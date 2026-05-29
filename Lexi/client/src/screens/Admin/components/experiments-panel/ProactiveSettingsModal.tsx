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
    Checkbox,
    FormControlLabel,
    FormGroup,
    Divider,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
} from '@mui/material';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { SnackbarStatus, useSnackbar } from '@contexts/SnackbarProvider';
import { updateExperiment } from '@DAL/server-requests/experiments';
import { ExperimentType, ProactiveHeuristicsSettings } from '@models/AppModels';

const LLM_MODEL_OPTIONS = [
    { value: 'gpt-4o',                        label: 'GPT-4o (OpenAI)' },
    { value: 'claude-3-5-sonnet-20241022',     label: 'Claude 3.5 Sonnet (Anthropic)' },
];

const DEFAULT_HEURISTICS: ProactiveHeuristicsSettings = {
    temporal: true,
    affective: true,
    behaviouralGap: true,
};

interface ProactiveSettingsModalProps {
    open: boolean;
    onClose: () => void;
    experiment: ExperimentType;
    onUpdate?: (updatedExperiment: ExperimentType) => void;
}

export const ProactiveSettingsModal: React.FC<ProactiveSettingsModalProps> = ({
    open,
    onClose,
    experiment,
    onUpdate,
}) => {
    const [proactiveEnabled, setProactiveEnabled] = useState(false);
    const [frequency, setFrequency] = useState(30);
    const [heuristics, setHeuristics] = useState<ProactiveHeuristicsSettings>(DEFAULT_HEURISTICS);
    const [llmModel, setLlmModel] = useState('gpt-4o');
    const serverBase = process.env.REACT_APP_API_URL || 'https://lexi-server-1rx9.onrender.com';
    const [deepLink, setDeepLink] = useState(`${serverBase}/join/${experiment._id}`);
    const [isLoading, setIsLoading] = useState(false);
    const { openSnackbar } = useSnackbar();

    // Sync state with experiment prop
    useEffect(() => {
        const ps = experiment.experimentFeatures?.proactiveSettings;
        if (ps) {
            setProactiveEnabled(ps.enabled);
            setFrequency(ps.frequency);
            setHeuristics({ ...DEFAULT_HEURISTICS, ...(ps.heuristics ?? {}) });
            setLlmModel(ps.llmModel ?? 'gpt-4o');
        } else {
            setProactiveEnabled(false);
            setFrequency(30);
            setHeuristics(DEFAULT_HEURISTICS);
            setLlmModel('gpt-4o');
        }
    }, [experiment]);

    const handleHeuristicToggle = (key: keyof ProactiveHeuristicsSettings) => {
        setHeuristics(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const handleSave = async () => {
        setIsLoading(true);
        try {
            // Create complete ExperimentType payload preserving all existing fields
            const updatedExperiment: ExperimentType = {
                ...experiment,  // Preserve all existing experiment fields
                experimentFeatures: {
                    // Preserve existing features if they exist
                    userAnnotation: experiment.experimentFeatures?.userAnnotation || false,
                    streamMessage: experiment.experimentFeatures?.streamMessage || false,
                    // Add/update proactive settings
                    proactiveSettings: {
                        enabled: proactiveEnabled,
                        frequency: frequency,
                        heuristics: heuristics,
                        llmModel: llmModel,
                    }
                }
            };

            // Use the DAL function with correct URL and axios instance
            await updateExperiment(updatedExperiment);
            
            // Call onUpdate to update parent state
            if (onUpdate) {
                onUpdate(updatedExperiment);
            }
            
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

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>
                <Box display="flex" alignItems="center" gap={1}>
                    <NotificationsActiveIcon />
                    Proactive Settings
                </Box>
            </DialogTitle>
            <DialogContent>
                <Box display="flex" flexDirection="column" gap={3}>
                    {/* Proactive Mode Toggle */}
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                        <Typography variant="body1">Enable Proactive Mode</Typography>
                        <Switch
                            checked={proactiveEnabled}
                            onChange={(e) => setProactiveEnabled(e.target.checked)}
                            color="primary"
                        />
                    </Box>

                    {/* Frequency Input */}
                    <Box>
                        <Typography variant="body1" gutterBottom>
                            Frequency (minutes)
                        </Typography>
                        <TextField
                            type="number"
                            value={frequency}
                            onChange={(e) => setFrequency(Number(e.target.value))}
                            size="small"
                            disabled={!proactiveEnabled}
                            helperText="How often to send proactive messages"
                            inputProps={{
                                min: 1,
                                max: 1440, // 24 hours max
                            }}
                        />
                    </Box>

                    <Divider />

                    {/* LLM Model Selector */}
                    <Box>
                        <Typography variant="body1" gutterBottom>
                            LLM Model
                        </Typography>
                        <FormControl size="small" fullWidth disabled={!proactiveEnabled}>
                            <InputLabel>Model</InputLabel>
                            <Select
                                value={llmModel}
                                label="Model"
                                onChange={(e) => setLlmModel(e.target.value)}
                            >
                                {LLM_MODEL_OPTIONS.map((opt) => (
                                    <MenuItem key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    <Divider />

                    {/* Heuristics Toggles */}
                    <Box>
                        <Typography variant="body1" gutterBottom>
                            Active Heuristics
                        </Typography>
                        <FormGroup>
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={heuristics.temporal}
                                        onChange={() => handleHeuristicToggle('temporal')}
                                        disabled={!proactiveEnabled}
                                        color="primary"
                                    />
                                }
                                label={
                                    <Box>
                                        <Typography variant="body2">Temporal</Typography>
                                        <Typography variant="caption" color="textSecondary">
                                            Reminds users of events they mentioned (e.g. "your exam is tomorrow")
                                        </Typography>
                                    </Box>
                                }
                            />
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={heuristics.affective}
                                        onChange={() => handleHeuristicToggle('affective')}
                                        disabled={!proactiveEnabled}
                                        color="primary"
                                    />
                                }
                                label={
                                    <Box>
                                        <Typography variant="body2">Affective</Typography>
                                        <Typography variant="caption" color="textSecondary">
                                            Follows up when high emotional load is detected in conversation
                                        </Typography>
                                    </Box>
                                }
                            />
                            <FormControlLabel
                                control={
                                    <Checkbox
                                        checked={heuristics.behaviouralGap}
                                        onChange={() => handleHeuristicToggle('behaviouralGap')}
                                        disabled={!proactiveEnabled}
                                        color="primary"
                                    />
                                }
                                label={
                                    <Box>
                                        <Typography variant="body2">Behavioural Gap</Typography>
                                        <Typography variant="caption" color="textSecondary">
                                            Asks about stated intentions that haven't been reported on (24–48 h gap)
                                        </Typography>
                                    </Box>
                                }
                            />
                        </FormGroup>
                    </Box>

                    <Divider />

                    {/* App Distribution Section */}
                    {proactiveEnabled && (
                        <Box>
                            <Typography variant="h6" gutterBottom>
                                Participant Join Link
                            </Typography>
                            <Typography variant="body2" color="textSecondary" gutterBottom>
                                Share this link with participants. Opening it on their Android device will download the Lexi app and automatically connect them to this experiment — no manual configuration needed.
                            </Typography>
                            <TextField
                                fullWidth
                                value={deepLink}
                                size="small"
                                disabled
                                InputProps={{
                                    endAdornment: (
                                        <Tooltip title="Copy link">
                                            <IconButton
                                                onClick={handleCopyLink}
                                                size="small"
                                                color="primary"
                                            >
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
                <Button onClick={handleSave} color="primary" variant="contained" disabled={isLoading}>
                    {isLoading ? 'Saving...' : 'Save'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
