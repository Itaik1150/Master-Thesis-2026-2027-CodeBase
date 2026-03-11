import { setActiveUser } from '@DAL/redux/reducers/activeUserReducer';
import { useAppDispatch, useAppSelector } from '@DAL/redux/store';
import { getActiveUser, logout } from '@DAL/server-requests/users';
import { setupFCMBridge } from '../services/fcmBridge';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

const useActiveUser = () => {
    const reduxUser = useAppSelector((state) => state.activeUser);
    const dispatch = useAppDispatch();
    const [isLoading, setIsLoading] = useState(true);
    const { experimentId } = useParams();

    useEffect(() => {
        const fetchUser = async () => {
            setIsLoading(true);
            try {
                const fetchedUser = await getActiveUser();
                dispatch(setActiveUser(fetchedUser));
                
                // Setup FCM bridge after successful authentication
                if (fetchedUser && !fetchedUser.isAdmin) {
                    try {
                        await setupFCMBridge();
                    } catch (error) {
                        console.warn('FCM Bridge setup failed:', error);
                    }
                }
            } catch (error) {
                dispatch(setActiveUser(null));
            }
            setIsLoading(false);
        };

        const handleLogout = async () => {
            if (reduxUser && !reduxUser.isAdmin && reduxUser.experimentId !== experimentId) {
                await logout();
                dispatch(setActiveUser(null));
            }
        };

        if (!reduxUser) {
            fetchUser();
        } else if (experimentId) {
            handleLogout();
        } else {
            setIsLoading(false);
        }
    }, [reduxUser, experimentId, dispatch]);

    // Additional effect for periodic token sync when user is active
    useEffect(() => {
        if (!reduxUser || reduxUser.isAdmin) {
            return;
        }

        // Sync token immediately when user becomes active
        const syncToken = async () => {
            try {
                const { getCurrentFCMToken } = await import('../services/fcmBridge');
                const { updateFCMToken } = await import('../DAL/server-requests/users');
                const currentToken = await getCurrentFCMToken();
                if (currentToken) {
                    await updateFCMToken(currentToken);
                    console.log('🔄 FCM token synced on user activation');
                }
            } catch (error) {
                console.warn('🔄 FCM token sync failed:', error);
            }
        };

        syncToken();

        // Set up periodic sync every 2 minutes
        const syncInterval = setInterval(syncToken, 2 * 60 * 1000);

        return () => clearInterval(syncInterval);
    }, [reduxUser]);

    return { activeUser: reduxUser, isLoading };
};

export default useActiveUser;
