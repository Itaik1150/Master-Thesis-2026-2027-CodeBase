import LoadingDots from '@components/loadig-dots/LoadingDots';
import { Box } from '@mui/material';
import { MessageType } from '@root/models/AppModels';
import Message from './Message';

interface MessageListProps {
    isMobile: boolean;
    messages: MessageType[];
    isMessageLoading: boolean;
    size: 'sm' | 'lg';
    handleUpdateUserAnnotation: (messageId, userAnnotation) => void;
    experimentHasUserAnnotation: boolean;
}

const MessageList: React.FC<MessageListProps> = ({
    isMobile,
    messages,
    isMessageLoading,
    size,
    experimentHasUserAnnotation,
    handleUpdateUserAnnotation,
}) => {
    // Multiple fallback checks to detect proactive opener:
    // 1. Primary: Check isProactiveOpener flag
    // 2. Fallback: If conversation has exactly 1 message and it's from assistant, 
    //    and we came from a notification (check URL/sessionStorage)
    const firstMessage = messages[0];
    const isFirstMessageFromAssistant = firstMessage?.role === 'assistant';
    const hasOnlyOneMessage = messages.length === 1;
    
    // Check if we came from a notification tap (set by deep link handler)
    const cameFromNotification = sessionStorage.getItem('fromNotification') === 'true';
    
    const showFeedbackOnFirstMessage = 
        hasOnlyOneMessage && 
        isFirstMessageFromAssistant && 
        (firstMessage?.isProactiveOpener === true || cameFromNotification);
    
    console.log('[MessageList] Proactive detection:', {
        hasOnlyOneMessage,
        isFirstMessageFromAssistant,
        isProactiveOpenerFlag: firstMessage?.isProactiveOpener,
        cameFromNotification,
        showFeedback: showFeedbackOnFirstMessage
    });
    
    return (
        <Box height="100%" width={isMobile ? '100%' : '85%'} padding={2}>
            {messages.map((message, index) => (
                <Message
                    key={index}
                    message={message}
                    role={message.role}
                    size={size}
                    handleUpdateUserAnnotation={handleUpdateUserAnnotation}
                    experimentHasUserAnnotation={experimentHasUserAnnotation}
                    showProactiveFeedback={index === 0 && showFeedbackOnFirstMessage}
                />
            ))}
            {isMessageLoading && <LoadingDots />}
        </Box>
    );
};

export default MessageList;
