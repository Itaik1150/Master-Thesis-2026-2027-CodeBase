import { Request, Response } from 'express';
import mongoose from 'mongoose';
import { conversationsService } from '../services/conversations.service';
import { experimentsService } from '../services/experiments.service';
import { formsService } from '../services/forms.service';
import { usersService } from '../services/users.service';
import { requestHandler } from '../utils/requestHandler';

// Strip IPv4-mapped IPv6 prefix so ::ffff:1.2.3.4 and 1.2.3.4 match.
const normalizeIp = (ip: string): string =>
    ip.startsWith('::ffff:') ? ip.slice(7) : ip;

const getClientIp = (req: Request): string => {
    const forwarded = req.headers['x-forwarded-for'];
    const raw = forwarded
        ? (Array.isArray(forwarded) ? forwarded[0] : forwarded).split(',')[0].trim()
        : req.socket?.remoteAddress || req.ip || 'unknown';
    return normalizeIp(raw);
};

class ExperimentsController {
    getExperiments = requestHandler(async (req: Request, res: Response) => {
        const page = req.query.page as string;
        const limit = req.query.limit as string;
        const experiments = await experimentsService.getExperiments(page, limit);
        res.status(200).send(experiments);
    });

    getExperiment = requestHandler(async (req: Request, res: Response) => {
        const experimentId = req.params.id as string;
        const experiments = await experimentsService.getExperiment(experimentId);
        res.status(200).send(experiments);
    });

    getExperimentContent = requestHandler(async (req: Request, res: Response) => {
        const experimentId = req.params.id as string;
        const experiment = await experimentsService.getExperiment(experimentId);
        res.status(200).send({ content: experiment.displaySettings, isActive: experiment.isActive });
    });

    createExperiment = requestHandler(async (req: Request, res: Response) => {
        const { experiment } = req.body;
        const savedExperiment = await experimentsService.createExperiment(experiment);
        res.status(200).send(savedExperiment);
    });

    updateExperimentsStatus = requestHandler(async (req: Request, res: Response) => {
        const { modifiedExperiments } = req.body;
        await experimentsService.updateExperimentsStatus(modifiedExperiments);
        res.status(200).send();
    });

    updateExperimentDisplaySetting = requestHandler(async (req: Request, res: Response) => {
        const { experimentId, displaySettings } = req.body;
        await experimentsService.updateExperimentDisplaySettings(experimentId, displaySettings);
        res.status(200).send();
    });

    updateExperiment = requestHandler(async (req: Request, res: Response) => {
        console.log('UPDATING EXPERIMENT:', req.body);
        const { experiment } = req.body;
        await experimentsService.updateExperiment(experiment);

        // When proactive is toggled ON, ensure existing users in this experiment
        // that already have an FCM token also get isProactive=true.
        // Handles the case where proactive was enabled after users already registered.
        const proactiveEnabled = experiment?.experimentFeatures?.proactiveSettings?.enabled;
        if (proactiveEnabled) {
            const db = mongoose.connection.db;
            const result = await db.collection('users').updateMany(
                {
                    experimentId: String(experiment._id),
                    fcmToken: { $exists: true, $ne: '' },
                    isProactive: { $ne: true },
                },
                { $set: { isProactive: true } },
            );
            if (result.modifiedCount > 0) {
                console.log(`[updateExperiment] set isProactive=true on ${result.modifiedCount} existing user(s) in experiment ${experiment._id}`);
            }
        }

        res.status(200).send();
    });

    getRegistrationForm = requestHandler(async (req: Request, res: Response) => {
        const experimentId = req.params.id as string;
        const experiment = await experimentsService.getExperiment(experimentId);
        if (experiment.experimentForms?.registration) {
            const form = await formsService.getForm(experiment.experimentForms?.registration);
            res.status(200).send(form);
            return;
        }
        res.status(200).send(null);
    });

    getConversationForms = requestHandler(async (req: Request, res: Response) => {
        const experimentId = req.params.id as string;
        const experiment = await experimentsService.getExperiment(experimentId);
        const forms = await formsService.getConversationForms(
            experiment.experimentForms?.preConversation,
            experiment.experimentForms?.postConversation,
        );
        res.status(200).send(forms);
    });

    getAllExperimentsByAgentId = requestHandler(async (req: Request, res: Response) => {
        const { agentId } = req.query;
        const experiments = await experimentsService.getAllExperimentsByAgentId(agentId as string);
        res.status(200).send(experiments);
    });

    getExperimentFeatures = requestHandler(async (req: Request, res: Response) => {
        const experimentId = req.params.id as string;
        const experimentFeatures = await experimentsService.getExperimentFeatures(experimentId);

        res.status(200).send(experimentFeatures);
    });

    deleteExperiment = requestHandler(async (req: Request, res: Response) => {
        const experimentId = req.params.id as string;
        await Promise.all([
            experimentsService.deleteExperiment(experimentId),
            usersService.deleteExperimentUsers(experimentId),
            conversationsService.deleteExperimentConversations(experimentId),
        ]);

        res.status(200).send();
    });

    // Called by the Android app on first launch.
    // Matches the device IP to the most recent unmatched apk_session within 60 minutes
    // and returns the associated experimentId so the app can lock itself in.
    matchSession = requestHandler(async (req: Request, res: Response) => {
        const ip = getClientIp(req);
        const windowStart = new Date(Date.now() - 60 * 60 * 1000);

        console.log(`[match-session] incoming IP: "${ip}"`);

        const db = mongoose.connection.db;

        // Use explicit findOne + updateOne instead of findOneAndUpdate to avoid
        // driver-version differences in return shape.
        const session = await db.collection('apk_sessions').findOne(
            { ip, timestamp: { $gte: windowStart }, matched: false },
            { sort: { timestamp: -1 } },
        );

        console.log(`[match-session] found session: ${session ? JSON.stringify(session) : 'none'}`);

        if (!session) {
            // Also log all recent sessions for this IP to help debug mismatches.
            const recent = await db.collection('apk_sessions')
                .find({ timestamp: { $gte: windowStart } })
                .sort({ timestamp: -1 })
                .limit(5)
                .toArray();
            console.log(`[match-session] recent sessions (last 5): ${JSON.stringify(recent.map(s => ({ ip: s.ip, expId: s.experimentId, matched: s.matched })))}`);
            res.status(404).json({ experimentId: null });
            return;
        }

        await db.collection('apk_sessions').updateOne(
            { _id: session._id },
            { $set: { matched: true, matchedAt: new Date() } },
        );

        res.status(200).json({ experimentId: session.experimentId });
    });
}

export const experimentsController = new ExperimentsController();
