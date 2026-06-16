import mongoose from 'mongoose';
import { IAgent } from '../types/agents.type';

export interface IUser {
    _id?: mongoose.Types.ObjectId;
    experimentId: string;
    username: string;
    age: number;
    gender: 'male' | 'female' | 'other';
    biologicalSex: string;
    maritalStatus: string;
    childrenNumber: number;
    nativeEnglishSpeaker: boolean;
    createdAt: Date;
    timestamp: number;
    isAdmin: boolean;
    password?: string;
    numberOfConversations: number;
    agent: IAgent;
    proactiveGroup?: 'affective' | 'generic' | 'reactive';
    fcmToken?: string;
    fcmTokenUpdatedAt?: Date;
    isProactive?: boolean;
    is_demo_finished?: boolean; // Demo termination flag (oxford-demo branch)
    demo_registration_time?: Date; // User registration timestamp for demo timing
}
