import { Pages } from '@app/App';
import useActiveUser from '@hooks/useActiveUser';
import { Box } from '@mui/system';
import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom';

const PrivateExperimentRoute = ({ TopBar, setIsOpen }) => {
    const { activeUser } = useActiveUser();
    const { experimentId } = useParams();
    const location = useLocation();

    if (!activeUser) {
        const loginPath = Pages.EXPERIMENT_LOGIN.replace(':experimentId', experimentId);
        // Preserve the full path (e.g. /e/:id/c/:convId) so login can redirect back.
        const returnTo = encodeURIComponent(location.pathname);
        return <Navigate to={`${loginPath}?returnTo=${returnTo}`} replace />;
    }

    return (
        <Box style={{ overflow: 'hidden', maxHeight: '100vh' }}>
            <TopBar setIsOpen={setIsOpen} />
            <Outlet />;
        </Box>
    );
};

export default PrivateExperimentRoute;
