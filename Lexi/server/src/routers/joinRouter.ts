import { Router } from 'express';
import { joinController } from '../controllers/joinController';

export const joinRouter = () => {
    const router = Router();
    // Landing page: participant opens this URL in their browser
    router.get('/:experimentId', joinController.landingPage);
    // Download trigger: logs IP + experimentId, then redirects to APK file
    router.get('/:experimentId/download', joinController.downloadApk);
    return router;
};
