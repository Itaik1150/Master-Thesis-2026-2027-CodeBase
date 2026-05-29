import { Pages } from '@app/App';
import useActiveUser from '@hooks/useActiveUser';
import { Navigate, Outlet, useParams, useSearchParams } from 'react-router-dom';

const LoginExperimentRoute = ({ TopBar, setIsOpen }) => {
    const { activeUser } = useActiveUser();
    const { experimentId } = useParams();
    const [searchParams] = useSearchParams();

    if (!activeUser) {
        return (
            <>
                <TopBar setIsOpen={setIsOpen} />
                <Outlet />
            </>
        );
    }

    // After login, go back to the intended destination (e.g. a specific conversation).
    // Fall back to the experiment home if no returnTo was specified.
    const returnTo = searchParams.get('returnTo');
    const destination = returnTo ? decodeURIComponent(returnTo) : Pages.EXPERIMENT.replace(':experimentId', experimentId);
    return <Navigate to={destination} replace />;
};

export default LoginExperimentRoute;
