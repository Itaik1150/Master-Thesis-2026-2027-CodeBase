import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Switch,
    TextField,
    Typography,
    Box,
    IconButton,
    Tooltip,
    Divider,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
    Collapse,
    Chip,
    Alert,
} from '@mui/material';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { SnackbarStatus, useSnackbar } from '@contexts/SnackbarProvider';
import { updateExperiment } from '@DAL/server-requests/experiments';
import {
    ExperimentType,
    HeuristicWeights,
    HeuristicPrompts,
} from '@models/AppModels';

// ── Supported LLM models ───────────────────────────────────────────────────────
const LLM_MODEL_OPTIONS = [
    { value: 'gpt-4o',                       label: 'GPT-4o (OpenAI)' },
    { value: 'gpt-4o-mini',                  label: 'GPT-4o Mini (OpenAI — cheaper)' },
    { value: 'claude-3-5-sonnet-20241022',   label: 'Claude 3.5 Sonnet (Anthropic)' },
    { value: 'claude-3-opus-20240229',       label: 'Claude 3 Opus (Anthropic — most capable)' },
];

// ── Heuristic metadata ─────────────────────────────────────────────────────────
type HeuristicKey = 'affective' | 'temporal' | 'behaviouralGap' | 'generic';

interface HeuristicMeta {
    label: string;
    description: string;
    hasMemoryPrompt: boolean;
    defaultMemoryPrompt: string;
    defaultMessagePrompt: string;
}

const HEURISTICS: Record<HeuristicKey, HeuristicMeta> = {
    affective: {
        label: 'Affective',
        description:
            'Scans the user\'s recent conversations for emotional content (stress, sadness, joy). ' +
            'When emotional expressions are found, sends a warm, personalised check-in referencing what the user shared.',
        hasMemoryPrompt: true,
        defaultMemoryPrompt:
            'You analyze conversation messages for deep emotional content.\n' +
            'Extract emotional expressions, personal struggles, vulnerable shares, and meaningful life events.\n\n' +
            'For each emotional share found, produce an object with:\n' +
            '  "content": exact quote or close paraphrase\n' +
            '  "affective_score": integer 1–10 (1=mild, 10=deeply personal)\n' +
            '  "timestamp_iso": today\'s ISO datetime\n' +
            '  "used": false\n\n' +
            'Return ONLY valid JSON: {"emotional_memories": [...]}\n' +
            'Return {"emotional_memories": []} if no genuine emotional content is present.',
        defaultMessagePrompt:
            'You are an empathetic assistant that encourages emotional sharing.\n' +
            'Generate a warm, personal emotional check-in in {language} (max 15 words) ' +
            'that directly references the specific emotional memory the user shared.\n' +
            'Acknowledge their feelings without being dramatic or clinical.\n' +
            'Invite them to share how they are feeling about it now.\n' +
            'Return ONLY the final message, no quotes or explanations.',
    },
    temporal: {
        label: 'Temporal',
        description:
            'Detects when the user has mentioned an upcoming event or plan. ' +
            'Sends a timely message asking how they are preparing — or, if the event just passed, how it went.',
        hasMemoryPrompt: true,
        defaultMemoryPrompt:
            'You analyze conversation messages for mentions of upcoming events, plans, appointments, or activities.\n\n' +
            'For each future event found, extract:\n' +
            '  "text": concise description (e.g. "job interview", "doctor appointment")\n' +
            '  "when_iso": ISO 8601 datetime string if timing is mentioned, or null if unclear\n\n' +
            'Today is {today_iso}. Resolve all relative dates against today.\n' +
            'Return ONLY valid JSON: {"future_mentions": [...]}\n' +
            'Return {"future_mentions": []} if no future events are mentioned.',
        defaultMessagePrompt:
            'You are a friendly assistant. Generate a warm, timely message in {language} (max 15 words) ' +
            'about the user\'s upcoming event or plan.\n' +
            'If the event is still ahead: ask if they are ready or excited.\n' +
            'If the event just passed: ask how it went.\n' +
            'Return ONLY the final message, no quotes or explanations.',
    },
    behaviouralGap: {
        label: 'Behavioural Gap',
        description:
            'Notices when the user stated an intention (e.g. "I\'ll go to the gym tomorrow") but has not mentioned it since. ' +
            'Sends a gentle follow-up to check whether they followed through.',
        hasMemoryPrompt: true,
        defaultMemoryPrompt:
            'You analyze conversation messages for EXPLICIT, concrete plans or commitments the user expressed.\n\n' +
            'Valid examples: "I\'ll go to the gym tomorrow", "I\'m starting that course next week"\n' +
            'Invalid (too vague): "I want to be healthier", "Maybe I\'ll try that someday"\n\n' +
            'Return JSON: {"intents": [{"intent": "concise English description"}]}\n' +
            'Return {"intents": []} if no clear commitments are found.',
        defaultMessagePrompt:
            'You are a supportive, caring assistant.\n' +
            'Generate a gentle, friendly follow-up message in {language} (max 15 words) ' +
            'asking whether the user followed through on their stated plan.\n' +
            'Do NOT assume success or failure — stay curious and supportive.\n' +
            'Return ONLY the final message, no quotes or explanations.',
    },
    generic: {
        label: 'Generic',
        description:
            'Sends a simple, friendly invitation to chat — no emotional framing, no specific topic. ' +
            'Used as a control condition or baseline.',
        hasMemoryPrompt: false,
        defaultMemoryPrompt: '',
        defaultMessagePrompt:
            'You are a standard assistant. Generate a completely neutral, friendly invitation to chat in {language} ' +
            '(max 15 words) with zero emotional weight and no specific topics. ' +
            'You MAY use the user\'s name once if it feels natural. ' +
            'Return ONLY the final message, no quotes or explanations.',
    },
};

const HEURISTIC_KEYS: HeuristicKey[] = ['affective', 'temporal', 'behaviouralGap', 'generic'];

// ── Component state types ──────────────────────────────────────────────────────
interface HeuristicRowState {
    enabled:       boolean;
    weight:        number;
    memoryPrompt:  string;
    messagePrompt: string;
    promptsOpen:   boolean; // local UI only, not persisted
}

type HeuristicConfigs = Record<HeuristicKey, HeuristicRowState>;

const buildDefaultConfigs = (): HeuristicConfigs =>
    HEURISTIC_KEYS.reduce((acc, key) => {
        acc[key] = {
            enabled:       false,
            weight:        0,
            memoryPrompt:  HEURISTICS[key].defaultMemoryPrompt,
            messagePrompt: HEURISTICS[key].defaultMessagePrompt,
            promptsOpen:   false,
        };
        return acc;
    }, {} as HeuristicConfigs);

const initConfigs = (
    weights?: HeuristicWeights,
    prompts?: HeuristicPrompts,
): HeuristicConfigs =>
    HEURISTIC_KEYS.reduce((acc, key) => {
        const w = (weights as any)?.[key] ?? 0;
        const p = (prompts as any)?.[key] ?? {};
        acc[key] = {
            enabled:       w > 0,
            weight:        w,
            memoryPrompt:  p.memoryPrompt  || HEURISTICS[key].defaultMemoryPrompt,
            messagePrompt: p.messagePrompt || HEURISTICS[key].defaultMessagePrompt,
            promptsOpen:   false,
        };
        return acc;
    }, {} as HeuristicConfigs);

// ── Props ──────────────────────────────────────────────────────────────────────
interface ProactiveSettingsModalProps {
    open:       boolean;
    onClose:    () => void;
    experiment: ExperimentType;
    onUpdate?:  (updatedExperiment: ExperimentType) => void;
}

// ── Component ──────────────────────────────────────────────────────────────────
export const ProactiveSettingsModal: React.FC<ProactiveSettingsModalProps> = ({
    open,
    onClose,
    experiment,
    onUpdate,
}) => {
    const [proactiveEnabled, setProactiveEnabled] = useState(false);
    const [frequency,        setFrequency]        = useState(30);
    const [llmModel,         setLlmModel]         = useState('gpt-4o');
    const [configs,          setConfigs]          = useState<HeuristicConfigs>(buildDefaultConfigs);
    const [isLoading,        setIsLoading]        = useState(false);

    const serverBase = process.env.REACT_APP_API_URL || 'https://lexi-server-1rx9.onrender.com';
    const deepLink   = `${serverBase}/join/${experiment._id}`;
    const { openSnackbar } = useSnackbar();

    // ── Sync state when experiment prop changes ────────────────────────────────
    useEffect(() => {
        const ps = experiment.experimentFeatures?.proactiveSettings;
        if (ps) {
            setProactiveEnabled(ps.enabled);
            setFrequency(ps.frequency ?? 30);
            setLlmModel(ps.llmModel ?? 'gpt-4o');
            setConfigs(initConfigs(ps.heuristicWeights, ps.heuristicPrompts));
        } else {
            setProactiveEnabled(false);
            setFrequency(30);
            setLlmModel('gpt-4o');
            setConfigs(buildDefaultConfigs());
        }
    }, [experiment]);

    // ── Derived state ──────────────────────────────────────────────────────────
    const totalWeight = HEURISTIC_KEYS.reduce(
        (sum, k) => sum + (configs[k].enabled ? (configs[k].weight || 0) : 0),
        0,
    );
    const anyEnabled   = HEURISTIC_KEYS.some(k => configs[k].enabled);
    const isWeightValid = !anyEnabled || totalWeight === 100;

    // ── Row handlers ───────────────────────────────────────────────────────────
    const toggleHeuristic = (key: HeuristicKey) => {
        setConfigs(prev => ({
            ...prev,
            [key]: {
                ...prev[key],
                enabled: !prev[key].enabled,
                // When turning off, reset weight to 0
                weight: prev[key].enabled ? 0 : prev[key].weight,
            },
        }));
    };

    const setWeight = (key: HeuristicKey, value: number) => {
        setConfigs(prev => ({
            ...prev,
            [key]: { ...prev[key], weight: Math.max(0, Math.min(100, value)) },
        }));
    };

    const setPrompt = (key: HeuristicKey, field: 'memoryPrompt' | 'messagePrompt', value: string) => {
        setConfigs(prev => ({
            ...prev,
            [key]: { ...prev[key], [field]: value },
        }));
    };

    const togglePromptsOpen = (key: HeuristicKey) => {
        setConfigs(prev => ({
            ...prev,
            [key]: { ...prev[key], promptsOpen: !prev[key].promptsOpen },
        }));
    };

    // ── Save ───────────────────────────────────────────────────────────────────
    const handleSave = async () => {
        if (!isWeightValid) {
            openSnackbar(
                `Active heuristic weights must sum to 100% (current: ${totalWeight}%)`,
                SnackbarStatus.ERROR,
            );
            return;
        }
        setIsLoading(true);
        try {
            // Build heuristicWeights (reactive = remainder so Python reads correctly)
            const heuristicWeights: HeuristicWeights = {
                affective:      configs.affective.enabled      ? configs.affective.weight      : 0,
                temporal:       configs.temporal.enabled       ? configs.temporal.weight       : 0,
                behaviouralGap: configs.behaviouralGap.enabled ? configs.behaviouralGap.weight : 0,
                generic:        configs.generic.enabled        ? configs.generic.weight        : 0,
                reactive:       Math.max(0, 100 - totalWeight),
            };

            // Build heuristicPrompts (only save if researcher customised them)
            const heuristicPrompts: HeuristicPrompts = HEURISTIC_KEYS.reduce((acc, key) => {
                const c = configs[key];
                const defaults = HEURISTICS[key];
                // Only write to DB if the prompt differs from the default
                const memDiff = c.memoryPrompt  !== defaults.defaultMemoryPrompt;
                const msgDiff = c.messagePrompt !== defaults.defaultMessagePrompt;
                if (memDiff || msgDiff) {
                    (acc as any)[key] = {
                        memoryPrompt:  memDiff ? c.memoryPrompt  : '',
                        messagePrompt: msgDiff ? c.messagePrompt : '',
                    };
                }
                return acc;
            }, {} as HeuristicPrompts);

            const updatedExperiment: ExperimentType = {
                ...experiment,
                experimentFeatures: {
                    userAnnotation: experiment.experimentFeatures?.userAnnotation || false,
                    streamMessage:  experiment.experimentFeatures?.streamMessage  || false,
                    proactiveSettings: {
                        enabled:          proactiveEnabled,
                        frequency,
                        heuristics:       experiment.experimentFeatures?.proactiveSettings?.heuristics, // keep legacy
                        heuristicWeights,
                        heuristicPrompts,
                        llmModel,
                    },
                },
            };

            await updateExperiment(updatedExperiment);
            if (onUpdate) onUpdate(updatedExperiment);
            openSnackbar('Proactive settings saved successfully', SnackbarStatus.SUCCESS);
            onClose();
        } catch (error) {
            console.error('Failed to save proactive settings:', error);
            openSnackbar('Failed to save settings', SnackbarStatus.ERROR);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCopyLink = () => {
        navigator.clipboard.writeText(deepLink);
        openSnackbar('Link copied to clipboard', SnackbarStatus.SUCCESS);
    };

    // ── Render ─────────────────────────────────────────────────────────────────
    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" gap={1}>
                    <NotificationsActiveIcon />
                    Proactive Settings
                </Box>
            </DialogTitle>

            <DialogContent>
                <Box display="flex" flexDirection="column" gap={3} pt={1}>

                    {/* ── Enable toggle ──────────────────────────────────────── */}
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                        <Typography variant="body1" fontWeight={500}>
                            Enable Proactive Mode
                        </Typography>
                        <Switch
                            checked={proactiveEnabled}
                            onChange={e => setProactiveEnabled(e.target.checked)}
                            color="primary"
                        />
                    </Box>

                    {/* ── Frequency ──────────────────────────────────────────── */}
                    <Box>
                        <Typography variant="body2" color="textSecondary" gutterBottom>
                            Notification Frequency (minutes)
                        </Typography>
                        <TextField
                            type="number"
                            value={frequency}
                            onChange={e => setFrequency(Number(e.target.value))}
                            size="small"
                            disabled={!proactiveEnabled}
                            helperText="Minimum interval between two notifications for the same user"
                            inputProps={{ min: 1, max: 1440 }}
                        />
                    </Box>

                    <Divider />

                    {/* ── LLM Model selector ─────────────────────────────────── */}
                    <Box>
                        <Typography variant="body1" fontWeight={500} gutterBottom>
                            LLM Model
                        </Typography>
                        <FormControl size="small" fullWidth disabled={!proactiveEnabled}>
                            <InputLabel>Model</InputLabel>
                            <Select
                                value={llmModel}
                                label="Model"
                                onChange={e => setLlmModel(e.target.value)}
                            >
                                {LLM_MODEL_OPTIONS.map(opt => (
                                    <MenuItem key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Typography variant="caption" color="textSecondary" sx={{ mt: 0.5, display: 'block' }}>
                            This controls which AI model generates all proactive notifications for this experiment.
                            Changing this affects message quality, cost, and generation style.
                            Make sure the corresponding API key is set in the server environment
                            (OPENAI_API_KEY for GPT models, ANTHROPIC_API_KEY for Claude models).
                        </Typography>
                    </Box>

                    <Divider />

                    {/* ── Heuristic probability weights ──────────────────────── */}
                    <Box>
                        <Typography variant="body1" fontWeight={500} gutterBottom>
                            Heuristic Probability Weights
                        </Typography>
                        <Typography variant="caption" color="textSecondary" sx={{ mb: 1, display: 'block' }}>
                            Each active heuristic is assigned a probability weight. On every cycle the system
                            randomly selects one according to those weights. The active weights must sum to
                            exactly 100%. If all heuristics are turned off, the system enters{' '}
                            <strong>Reactive mode</strong> — no notifications will be sent.
                        </Typography>

                        {/* Heuristic rows */}
                        <Box display="flex" flexDirection="column" gap={1.5}>
                            {HEURISTIC_KEYS.map(key => {
                                const meta = HEURISTICS[key];
                                const cfg  = configs[key];
                                return (
                                    <Box
                                        key={key}
                                        sx={{
                                            border: '1px solid',
                                            borderColor: cfg.enabled ? 'primary.main' : 'divider',
                                            borderRadius: 2,
                                            p: 1.5,
                                            opacity: proactiveEnabled ? 1 : 0.5,
                                            transition: 'border-color 0.2s',
                                        }}
                                    >
                                        {/* Row header: toggle + name + weight input */}
                                        <Box display="flex" alignItems="center" gap={1}>
                                            <Switch
                                                size="small"
                                                checked={cfg.enabled}
                                                onChange={() => toggleHeuristic(key)}
                                                disabled={!proactiveEnabled}
                                                color="primary"
                                            />
                                            <Box flex={1}>
                                                <Typography variant="body2" fontWeight={500}>
                                                    {meta.label}
                                                </Typography>
                                                <Typography variant="caption" color="textSecondary">
                                                    {meta.description}
                                                </Typography>
                                            </Box>
                                            <TextField
                                                type="number"
                                                label="Weight %"
                                                value={cfg.weight}
                                                onChange={e => setWeight(key, Number(e.target.value))}
                                                size="small"
                                                disabled={!proactiveEnabled || !cfg.enabled}
                                                inputProps={{ min: 0, max: 100 }}
                                                sx={{ width: 100 }}
                                            />
                                        </Box>

                                        {/* Collapsible prompt editor */}
                                        {cfg.enabled && (
                                            <Box mt={1}>
                                                <Button
                                                    size="small"
                                                    onClick={() => togglePromptsOpen(key)}
                                                    endIcon={cfg.promptsOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                                    sx={{ textTransform: 'none', px: 0, color: 'text.secondary' }}
                                                >
                                                    Edit LLM Prompts
                                                </Button>
                                                <Collapse in={cfg.promptsOpen}>
                                                    <Box
                                                        display="flex"
                                                        flexDirection="column"
                                                        gap={1.5}
                                                        mt={1}
                                                        pl={1}
                                                        sx={{ borderLeft: '2px solid', borderColor: 'primary.light' }}
                                                    >
                                                        {meta.hasMemoryPrompt && (
                                                            <TextField
                                                                label="Memory Prompt"
                                                                multiline
                                                                rows={4}
                                                                fullWidth
                                                                size="small"
                                                                value={cfg.memoryPrompt}
                                                                onChange={e => setPrompt(key, 'memoryPrompt', e.target.value)}
                                                                helperText="Instructs the LLM on what to extract from conversations (create_memory phase)."
                                                            />
                                                        )}
                                                        <TextField
                                                            label="Message Prompt"
                                                            multiline
                                                            rows={4}
                                                            fullWidth
                                                            size="small"
                                                            value={cfg.messagePrompt}
                                                            onChange={e => setPrompt(key, 'messagePrompt', e.target.value)}
                                                            helperText="Instructs the LLM on what kind of proactive message to generate (get_proactive_message phase). Use {language} as a placeholder for the user's language."
                                                        />
                                                        <Button
                                                            size="small"
                                                            variant="outlined"
                                                            color="warning"
                                                            sx={{ alignSelf: 'flex-start', textTransform: 'none' }}
                                                            onClick={() => setConfigs(prev => ({
                                                                ...prev,
                                                                [key]: {
                                                                    ...prev[key],
                                                                    memoryPrompt:  meta.defaultMemoryPrompt,
                                                                    messagePrompt: meta.defaultMessagePrompt,
                                                                },
                                                            }))}
                                                        >
                                                            Reset to defaults
                                                        </Button>
                                                    </Box>
                                                </Collapse>
                                            </Box>
                                        )}
                                    </Box>
                                );
                            })}
                        </Box>

                        {/* Weight sum indicator */}
                        <Box display="flex" alignItems="center" gap={1} mt={2}>
                            <Typography variant="body2" color="textSecondary">
                                Total active weight:
                            </Typography>
                            <Chip
                                label={`${totalWeight}%`}
                                color={!anyEnabled ? 'default' : isWeightValid ? 'success' : 'error'}
                                size="small"
                            />
                            {anyEnabled && !isWeightValid && (
                                <Typography variant="caption" color="error">
                                    Must equal 100% before saving
                                </Typography>
                            )}
                        </Box>

                        {/* Reactive mode info */}
                        {!anyEnabled && (
                            <Alert severity="info" sx={{ mt: 1.5 }}>
                                All heuristics are off — the system will enter{' '}
                                <strong>Reactive mode</strong> and send no proactive notifications.
                            </Alert>
                        )}
                    </Box>

                    <Divider />

                    {/* ── Participant join link ───────────────────────────────── */}
                    {proactiveEnabled && (
                        <Box>
                            <Typography variant="h6" gutterBottom>
                                Participant Join Link
                            </Typography>
                            <Typography variant="body2" color="textSecondary" gutterBottom>
                                Share this link with participants. Opening it on their Android device will
                                download the Lexi app and automatically connect them to this experiment —
                                no manual configuration needed.
                            </Typography>
                            <TextField
                                fullWidth
                                value={deepLink}
                                size="small"
                                disabled
                                InputProps={{
                                    endAdornment: (
                                        <Tooltip title="Copy link">
                                            <IconButton onClick={handleCopyLink} size="small" color="primary">
                                                <ContentCopyIcon />
                                            </IconButton>
                                        </Tooltip>
                                    ),
                                }}
                            />
                        </Box>
                    )}

                </Box>
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} color="secondary">
                    Close
                </Button>
                <Button
                    onClick={handleSave}
                    color="primary"
                    variant="contained"
                    disabled={isLoading || (anyEnabled && !isWeightValid)}
                >
                    {isLoading ? 'Saving…' : 'Save'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
