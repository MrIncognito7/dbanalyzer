import ChatbotIcon from "./ChatbotIcon";

const ChatMessage = ({ chat }) => {
  const isBot = chat.role === "model";
  return (
    <div className={`message ${isBot ? "bot" : "user"}-message`}>
      {isBot && <ChatbotIcon />}
      <p className={`message-text${chat.isError ? " error" : ""}`}>{chat.text}</p>
    </div>
  );
};

export default ChatMessage;
