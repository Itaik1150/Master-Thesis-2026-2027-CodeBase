import { setActiveUser } from '@DAL/redux/reducers/activeUserReducer';
import { registerUser } from '@DAL/server-requests/users';
import { SnackbarStatus, useSnackbar } from '@contexts/SnackbarProvider';
import { NewUserInfoType } from '@models/AppModels';
import { Box, CircularProgress, Container } from '@mui/material';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useDispatch } from 'react-redux';
import { useLocation, useNavigate } from 'react-router-dom';
import { Pages } from '@app/App';
import { getExperimentRegistrationForm } from '../../DAL/server-requests/experiments';
import useEffectAsync from '../../hooks/useEffectAsync';
import { FirstRegisterForm } from './FirstRegistrationForm';
import { FinalRegisterForm } from './final-register-form/FinalRegistrationForm';
import TermsOfConditions from './terms-of-conditions/TermsOfConditions';

interface RegisterFormProps {
    experimentId: string;
    setShowFormTypeButtons: (show: boolean) => void;
}

async function registerDeviceInYourServer(payload: {
    userId: string;
    fcmToken: string;
    experimentId: string;
}) {
    await fetch("http://localhost:5000/register-device", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}



export const RegisterForm: React.FC<RegisterFormProps> = ({ experimentId, setShowFormTypeButtons }) => {
    const [page, setPage] = useState(1);
    const [form, setForm] = useState(null);
    const dispatch = useDispatch();
    const navigate = useNavigate();
    const location = useLocation();
    const { openSnackbar } = useSnackbar();
    const [isAgreedTerms, setIsAgreedTerms] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    const {
        register,
        handleSubmit,
        setError,
        getValues,
        setValue,
        control,
        formState: { errors },
    } = useForm();

    const goToPage = (newPage: number) => {
        if (newPage === 1) {
            setShowFormTypeButtons(true);
        } else {
            setShowFormTypeButtons(false);
        }
        setPage(newPage);
    };

    useEffectAsync(async () => {
        const res = await getExperimentRegistrationForm(experimentId);
        setForm(res);
        setIsLoading(false);
    }, []);

    const getFCMTokenWithRetry = async (retries = 3, delay = 2000): Promise<string> => {
        for (let i = 0; i < retries; i++) {
            try {
                const token = (window as any)?.Android?.getFCMToken?.() || '';
                if (token && token.trim() !== '') {
                    console.log('FCM token retrieved successfully');
                    return token;
                }
            } catch (error) {
                console.warn(`FCM token retrieval attempt ${i + 1} failed:`, error);
            }
            
            if (i < retries - 1) {
                console.log(`FCM token empty, retrying in ${delay}ms... (${i + 1}/${retries})`);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
        console.warn('FCM token could not be retrieved after retries - continuing without FCM');
        return '';
    };

    const onSubmit = async (data: NewUserInfoType) => {
        try {
            // Get FCM token with retry mechanism
            let fcmToken = '';
            try {
                fcmToken = await getFCMTokenWithRetry();
            } catch (fcmError) {
                console.warn('FCM token retrieval failed, continuing without FCM:', fcmError);
            }

            // Register user (with or without FCM token)
            const user = await registerUser(data, experimentId, fcmToken);

            // Get the real user ID
            const userId = String((user as any)._id);

            // Try to register device only if we have a token and it's not already registered
            if (fcmToken && !user.fcmToken) {
                try {
                    await registerDeviceInYourServer({
                        userId,
                        fcmToken,
                        experimentId,
                    });
                } catch (backupError) {
                    console.warn('Backup FCM registration failed:', backupError);
                    // Continue even if FCM registration fails
                }
            }

            // Continue with normal flow
            dispatch(setActiveUser(user));
            const returnTo = new URLSearchParams(location.search).get('returnTo');
            const destination = returnTo
                ? decodeURIComponent(returnTo)
                : Pages.EXPERIMENT.replace(':experimentId', experimentId);
            navigate(destination);
            
        } catch (error) {
            console.error('Registration error:', error);
            
            // Handle specific error cases
            if (error?.response?.status === 403) {
                openSnackbar('Experiment Is Not Active', SnackbarStatus.ERROR);
                return;
            } else if (error?.response?.status === 401) {
                openSnackbar('Username Already Exists', SnackbarStatus.ERROR);
                return;
            } else if (error?.code === 'NETWORK_ERROR' || error?.message?.includes('Network Error')) {
                openSnackbar('Network Error - Please check your connection', SnackbarStatus.ERROR);
                return;
            }
            
            openSnackbar('Registration Failed - Please try again', SnackbarStatus.ERROR);
        }
    };


    const handleFirstRegistrationSubmit = async (data: NewUserInfoType) => {
        if (form?.termsOfConditions) {
            goToPage(2);
        } else if (form) {
            goToPage(3);
        } else {
            await onSubmit(data);
        }
    };

    const handleTermsOfConditionSubmit = () => {
        if (form) {
            goToPage(3);
        } else {
            handleSubmit(onSubmit)();
        }
    };

    return (
        <Container component="main" maxWidth={page !== 1 ? 'sm' : 'xs'}>
            <Box display={'flex'} justifyContent={'center'} marginTop={page === 2 ? 0 : 3}>
                {isLoading ? (
                    <CircularProgress size={80} />
                ) : page === 1 ? (
                    <FirstRegisterForm
                        setPage={goToPage}
                        getValues={getValues}
                        setError={setError}
                        handleSubmit={handleSubmit}
                        setValue={setValue}
                        experimentId={experimentId}
                        register={register}
                        errors={errors}
                        onSubmit={handleFirstRegistrationSubmit}
                        buttonLabel={!form && !form?.termsOfConditions ? 'Sign Up' : 'Continue'}
                    />
                ) : page === 2 ? (
                    <TermsOfConditions
                        setPage={goToPage}
                        isAgreed={isAgreedTerms}
                        setIsAgreed={setIsAgreedTerms}
                        onSubmit={handleTermsOfConditionSubmit}
                    />
                ) : (
                    <FinalRegisterForm
                        setValue={setValue}
                        register={register}
                        errors={errors}
                        getValues={getValues}
                        handleSubmit={handleSubmit(onSubmit)}
                        setPage={goToPage}
                        handleGoBack={() => (form?.termsOfConditions ? goToPage(2) : goToPage(1))}
                        control={control}
                        form={form}
                    />
                )}
            </Box>
        </Container>
    );
};
