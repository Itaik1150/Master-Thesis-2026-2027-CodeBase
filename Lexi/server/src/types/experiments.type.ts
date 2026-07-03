import mongoose from 'mongoose';

export interface ABAgents {
    agentA: string;
    distA: number;
    agentB: string;
    distB: number;
}

export interface DisplaySettings {
    welcomeContent: string;
    welcomeHeader: string;
}

export interface ExperimentForms {
    registration: string;
    preConversation: string;
    postConversation: string;
}

export interface ProactiveHeuristicsSettings {
    temporal: boolean;
    affective: boolean;
    behaviouralGap: boolean;
}

/** Probability weights for heuristic selection (must sum to 100). */
export interface HeuristicWeights {
    affective:      number;
    temporal:       number;
    behaviouralGap: number;
    generic:        number;
    reactive?:      number; // 100 - sum(others); managed by UI, not entered by researcher
}

/** A memory/message prompt pair for one heuristic. */
export interface HeuristicPromptPair {
    memoryPrompt?:  string;
    messagePrompt?: string;
}

/** Per-heuristic LLM prompts set by the researcher in the dashboard. */
export interface HeuristicPrompts {
    affective?:      HeuristicPromptPair;
    temporal?:       HeuristicPromptPair;
    behaviouralGap?: HeuristicPromptPair;
    generic?:        HeuristicPromptPair;
}

export interface ExperimentFeatures {
    userAnnotation: boolean;
    streamMessage: boolean;
    proactiveSettings?: {
        enabled: boolean;
        frequency: number; // in minutes
        heuristics?:       ProactiveHeuristicsSettings; // legacy boolean flags (backward compat)
        heuristicWeights?: HeuristicWeights;            // Task 3.1 — probability-based selection
        heuristicPrompts?: HeuristicPrompts;            // Task 4.2 — per-heuristic prompt editor
        llmModel?: string; // e.g. "gpt-4o" | "claude-3-5-sonnet-20241022"
    };
}

export interface IExperimentLean {
    _id: mongoose.Types.ObjectId;
    title: string;
}

export interface IExperiment {
    _id: mongoose.Types.ObjectId;
    agentsMode: string;
    activeAgent: string;
    abAgents: ABAgents;
    createdAt: Date;
    timestamp: number;
    displaySettings: DisplaySettings;
    isActive: boolean;
    title: string;
    description: string;
    numberOfParticipants: number;
    experimentForms: ExperimentForms;
    maxMessages: number;
    maxConversations: number;
    maxParticipants: number;
    totalSessions: number;
    openSessions: number;
    experimentFeatures: ExperimentFeatures;
}
