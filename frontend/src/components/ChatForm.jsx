
import { useRef } from "react";

const ChatForm = ({ onSend, disabled }) => {
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = inputRef.current.value.trim();
    if (!text || disabled) return;
    inputRef.current.value = "";
    onSend(text);
  };

  return (
    <form className="chat-form" onSubmit={handleSubmit}>
      <input
        ref={inputRef}
        type="text"
        placeholder={disabled ? "Thinking..." : "Ask something..."}
        className="message-input"
        maxLength={1000}
        disabled={disabled}
        required
        autoFocus
      />
      <button className="material-symbols-rounded" aria-label="Send" disabled={disabled}>
        arrow_upward
      </button>
    </form>
  );
};

export default ChatForm;
