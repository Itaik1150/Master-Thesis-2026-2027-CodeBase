import { Schema } from 'mongoose';
import { mongoDbProvider } from '../mongoDBProvider';
import { ABAgents, IExperiment } from '../types';

const AbAgentsSchema = new Schema<ABAgents>({
    distA: { type: Number, required: true },
    agentA: { type: String, required: true },
    distB: { type: Number, required: true },
    agentB: { type: String, required: true },
});

export const experimentsSchema = new Schema<IExperiment>(
    {
        agentsMode: { type: String, required: true },
        activeAgent: { type: String },
        abAgents: { type: AbAgentsSchema },
        createdAt: { type: Date, default: Date.now },
        timestamp: { type: Number, default: () => Date.now() },
        displaySettings: { type: Object },
        isActive: { type: Boolean },
        title: { type: String },
        description: { type: String },
        numberOfParticipants: { type: Number, default: () => 0 },
        experimentForms: {
            registration: { type: String },
            preConversation: { type: String },
            postConversation: { type: String },
        },
        maxMessages: { type: Number },
        maxConversations: { type: Number },
        maxParticipants: { type: Number },
        totalSessions: { type: Number, default: () => 0 },
        openSessions: { type: Number, default: () => 0 },
        experimentFeatures: {
            userAnnotation: { type: Boolean },
            streamMessage: { type: Boolean },
            proactiveSettings: {
                enabled: { type: Boolean, default: false },
                frequency: { type: Number, default: 30 },
                heuristics: {
                    temporal:       { type: Boolean, default: true },
                    affective:      { type: Boolean, default: true },
                    behaviouralGap: { type: Boolean, default: true },
                },
                heuristicWeights: {
                    affective:      { type: Number, default: 0 },
                    temporal:       { type: Number, default: 0 },
                    behaviouralGap: { type: Number, default: 0 },
                    generic:        { type: Number, default: 0 },
                    reactive:       { type: Number, default: 100 },
                },
                heuristicPrompts: {
                    affective:      { memoryPrompt: { type: String, default: '' }, messagePrompt: { type: String, default: '' } },
                    temporal:       { memoryPrompt: { type: String, default: '' }, messagePrompt: { type: String, default: '' } },
                    behaviouralGap: { memoryPrompt: { type: String, default: '' }, messagePrompt: { type: String, default: '' } },
                    generic:        { memoryPrompt: { type: String, default: '' }, messagePrompt: { type: String, default: '' } },
                },
                llmModel: { type: String, default: 'gpt-4o' },
            }
        },
    },
    { versionKey: false },
);

export const ExperimentsModel = mongoDbProvider.getModel('experiments', experimentsSchema);
