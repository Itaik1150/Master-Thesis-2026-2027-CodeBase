// Login.tsx
import { LoginForm } from '@components/forms/LoginForm';
import { RegisterForm } from '@components/forms/RegisterForm';
import { useExperimentId } from '@hooks/useExperimentId';
import { Box, Typography, useMediaQuery } from '@mui/material';
import theme from '@root/Theme';
import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { DividerButtonsContainer, FormSide, FormTypeButton, MainContainer } from './Login.s';

const DEMO_EXPERIMENT_ID = '6a32e516d3d79d396942bff3';

const Login: React.FC = () => {
    const location = useLocation();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const [firstPathSegment] = location.pathname.split('/').slice(1);
    const isAdminPage = firstPathSegment === 'admin';
    const [isSignUp, setIsSignUp] = useState(!isAdminPage);
    const [showFormTypeButtons, setShowFormTypeButtons] = useState(true);
    const experimentId = useExperimentId();
    const isDemo = experimentId === DEMO_EXPERIMENT_ID;

    return (
        <MainContainer>
            <FormSide elevation={4} isMobile={isMobile}>
                {isDemo && (
                    <Box style={{ textAlign: 'center', padding: '16px 8px 4px' }}>
                        <Typography variant="h5" fontWeight={700}>
                            Welcome to EIF CogAI 2026!
                        </Typography>
                    </Box>
                )}
                {showFormTypeButtons && (
                    <DividerButtonsContainer>
                        {!isAdminPage && (
                            <FormTypeButton variant="text" onClick={() => setIsSignUp(true)} isSignUp={isSignUp}>
                                First Time
                            </FormTypeButton>
                        )}
                        <FormTypeButton variant="text" onClick={() => setIsSignUp(false)} isSignUp={!isSignUp}>
                            {!isAdminPage ? 'Not First Time?' : 'Sign In'}
                        </FormTypeButton>
                    </DividerButtonsContainer>
                )}
                <Box style={{ flex: '1 1 auto' }}>
                    {isSignUp ? (
                        <RegisterForm
                            experimentId={experimentId}
                            setShowFormTypeButtons={setShowFormTypeButtons}
                        />
                    ) : (
                        <LoginForm isAdminPage={isAdminPage} experimentId={experimentId} />
                    )}
                </Box>
                {isDemo && (
                    <Box style={{ textAlign: 'center', padding: '8px 8px 14px', color: '#666', fontSize: '0.78rem' }}>
                        Itai Kohn | Dr. Guy Laban | Ben-Gurion University of the Negev
                    </Box>
                )}
            </FormSide>
        </MainContainer>
    );
};

export default Login;
