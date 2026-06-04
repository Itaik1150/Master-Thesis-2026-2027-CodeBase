import { useExperimentId } from '@hooks/useExperimentId';
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    useMediaQuery,
} from '@mui/material';
import theme from '@root/Theme';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { finishConversation } from '../../DAL/server-requests/conversations';
import { Pages } from '../../app/App';
import useActiveUser from '../../hooks/useActiveUser';
import { useConversationId } from '../../hooks/useConversationId';
import { ConversationForm } from '../forms/conversation-form/ConversationForm';

const FinishConversationDialog = ({ open, setIsOpen, questionnaireLink, form }) => {
    const [page, setPage] = useState(1);
    const { activeUser } = useActiveUser();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const experimentId = useExperimentId();
    const conversationId = useConversationId();
    const navigate = useNavigate();

    const handleYes = () => {
        if (form) {
            setPage(2);
        } else {
            setPage(3);
            handleDone();
        }
    };

    const handleNo = () => setIsOpen(false);

    const handleDone = async () => {
        try {
            await finishConversation(conversationId, experimentId, activeUser.isAdmin);
        } catch (error) {
            console.error('Failed to finish conversation');
        }
        console.log('Finish Conversation');
    };

    const handleDoneSurvey = async () => {
        if (questionnaireLink) {
            setPage(3);
        }
        handleDone();
    };

    return (
        <Dialog open={open} maxWidth={'lg'} fullScreen={isMobile && page > 1}>
            {page === 1 ? (
                <>
                    <DialogContent>
                        <DialogContentText color={'black'}>
                            Are you sure you want to finish the conversation?
                        </DialogContentText>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={handleNo}>No</Button>
                        <Button onClick={handleYes} autoFocus>
                            Yes
                        </Button>
                    </DialogActions>
                </>
            ) : page === 2 && form ? (
                <ConversationForm form={form} isPreConversation={false} handleDone={handleDoneSurvey} />
            ) : page === 3 || (!form && questionnaireLink) ? (
                <DialogContent
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        textAlign: 'center',
                        gap: 3,
                        py: 5,
                        px: 4,
                        minHeight: 220,
                    }}
                >
                    <DialogContentText color={'black'} sx={{ fontSize: '1.1rem', fontWeight: 500 }}>
                        Thank you for completing the conversation
                    </DialogContentText>
                    <DialogContentText color={'black'}>
                        Your username is <b>{activeUser.username}</b>, continue with it in the rest of the study.
                    </DialogContentText>
                    <Button
                        variant="contained"
                        onClick={() => {
                            navigate(`${Pages.EXPERIMENT.replace(':experimentId', experimentId)}`);
                            setIsOpen(false);
                        }}
                    >
                        Back to Home
                    </Button>
                </DialogContent>
            ) : null}
        </Dialog>
    );
};

export default FinishConversationDialog;
