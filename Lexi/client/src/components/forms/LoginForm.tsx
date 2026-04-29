import { setActiveUser } from '@DAL/redux/reducers/activeUserReducer';
import axiosInstance from '@DAL/server-requests/AxiosInstance';
import { login } from '@DAL/server-requests/users';
import { Pages } from '@app/App';
import { Box, Container, Grid, TextField } from '@mui/material';
import { getFormErrorMessage } from '@utils/commonFunctions';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { FormButton, NoteText } from './CommonFormStyles.s';

const getFCMTokenWithRetry = async (retries = 3, delay = 2000): Promise<string> => {
    for (let i = 0; i < retries; i++) {
        const token = (window as any)?.Android?.getFCMToken?.() || '';
        if (token) {
            console.log('FCM token retrieved successfully');
            return token;
        }
        if (i < retries - 1) {
            console.log(`FCM token empty, retrying in ${delay}ms... (${i + 1}/${retries})`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    console.warn('FCM token could not be retrieved after retries');
    return '';
};

const registerDeviceInYourServer = async (payload: {
    userId: string;
    fcmToken: string;
    experimentId: string;
}) => {
    await axiosInstance.post('/users/register-device', payload);
};

interface LoginFormProps {
    isAdminPage: boolean;
    experimentId: string;
}


export const LoginForm: React.FC<LoginFormProps> = ({ isAdminPage, experimentId }) => {
    const navigate = useNavigate();
    const dispatch = useDispatch();
    const [isUserAdmin, setIsUserAdmin] = useState(false);
    const {
        register,
        handleSubmit,
        setError,
        formState: { errors },
    } = useForm();

    const onSubmit = async (data) => {
        try {
            const { token, user } = await login(data.username, data.password, experimentId);

            if (user.isAdmin && !token) {
                setIsUserAdmin(true);
            } else if (user) {
                dispatch(setActiveUser(user));
                
                // Handle FCM token registration for non-admin users
                if (!user.isAdmin) {
                    try {
                        const userId = String(user._id);
                        const fcmToken = await getFCMTokenWithRetry();
                        
                        if (fcmToken) {
                            await registerDeviceInYourServer({
                                userId,
                                fcmToken,
                                experimentId,
                            });
                        } else {
                            console.warn('FCM token is empty - skipping device registration');
                        }
                    } catch (fcmError) {
                        console.warn('FCM token registration failed:', fcmError);
                        // Continue with login even if FCM registration fails
                    }
                }
                
                navigate(isAdminPage ? Pages.ADMIN : Pages.EXPERIMENT.replace(':experimentId', experimentId));
            }
        } catch (error) {
            console.error(error);
            if (error.response && error.response.status === 401) {
                setError('username', {
                    type: 'manual',
                    message: `User name ${
                        isUserAdmin || isAdminPage ? 'or Password are' : 'is'
                    } Invalid, Try again or Sign Up`,
                });
            } else {
                setError('username', { type: 'manual', message: 'Something went wrong, please try again later' });
            }
        }
    };

    return (
        <Container component="main" maxWidth="xs">
            <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate padding={2}>
                <Grid container spacing={2}>
                    <Grid item xs={12}>
                        {!isAdminPage && <NoteText>Please use the same username you signed up with.</NoteText>}
                        <TextField
                            error={Boolean(errors.username)}
                            helperText={getFormErrorMessage(errors.username)}
                            required
                            fullWidth
                            size="small"
                            {...register('username', { required: 'Please fill out username' })}
                            label="User Name"
                            id="username"
                        />
                    </Grid>
                    <Grid item xs={12}>
                        {(isAdminPage || isUserAdmin) && (
                            <TextField
                                error={Boolean(errors.password)}
                                helperText={getFormErrorMessage(errors.password)}
                                required
                                fullWidth
                                {...register('password', { required: 'Password is required' })}
                                label="Password"
                                type="password"
                                id="password"
                                size="small"
                                autoComplete="current-password"
                            />
                        )}
                    </Grid>
                </Grid>
                <Box display="flex" justifyContent="center">
                    <FormButton type="submit">Login</FormButton>
                </Box>
            </Box>
        </Container>
    );
};
