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
} from '@mui/material';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { SnackbarStatus, useSnackbar } from '@contexts/SnackbarProvider';
import { updateExperiment } from '@DAL/server-requests/experiments';
import { ExperimentType } from '@models/AppModels';

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
    const [deepLink, setDeepLink] = useState(`lexi://join/${experiment._id}`);
    const [isLoading, setIsLoading] = useState(false);
    const { openSnackbar } = useSnackbar();

    // Sync state with experiment prop
    useEffect(() => {
        const proactiveSettings = experiment.experimentFeatures?.proactiveSettings;
        if (proactiveSettings) {
            setProactiveEnabled(proactiveSettings.enabled);
            setFrequency(proactiveSettings.frequency);
        } else {
            // Reset to defaults if no settings exist
            setProactiveEnabled(false);
            setFrequency(30);
        }
    }, [experiment]);

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
                        frequency: frequency
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

                    {/* App Distribution Section */}
                    {proactiveEnabled && (
                        <Box>
                            <Typography variant="h6" gutterBottom>
                                App Distribution
                            </Typography>
                            <Typography variant="body2" color="textSecondary" gutterBottom>
                                Share this link with participants. When clicked on an Android device with Lexi installed, it will automatically connect them to this experiment.
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
