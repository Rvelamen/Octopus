import React, { useEffect, useRef, useState } from "react";
import { TerminalSquare } from "lucide-react";
import "./SlashCommandMenu.css";

function SlashCommandMenu({
  open,
  query,
  options,
  activeIndex,
  onSelect,
  onHover,
  textareaRef,
}) {
  const activeItemRef = useRef(null);
  const menuRef = useRef(null);
  const [position, setPosition] = useState(null);

  useEffect(() => {
    if (open && textareaRef?.current) {
      const rect = textareaRef.current.getBoundingClientRect();
      setPosition({
        left: rect.left,
        width: rect.width,
        bottom: window.innerHeight - rect.top + 8,
      });
    }
  }, [open, textareaRef]);

  useEffect(() => {
    if (!open) return;
    const handleResize = () => {
      if (textareaRef?.current) {
        const rect = textareaRef.current.getBoundingClientRect();
        setPosition({
          left: rect.left,
          width: rect.width,
          bottom: window.innerHeight - rect.top + 8,
        });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [open, textareaRef]);

  useEffect(() => {
    if (open && activeItemRef.current) {
      activeItemRef.current.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [open, activeIndex]);

  if (!open || !position) {
    return null;
  }

  return (
    <div
      ref={menuRef}
      className="slash-command-menu"
      style={{
        left: position.left,
        width: position.width,
        bottom: position.bottom,
      }}
    >
      <div className="slash-command-menu-inner">
        {options.length > 0 ? (
          <>
            <div className="slash-command-header">Slash Commands [{activeIndex + 1}/{options.length}]</div>
            <div className="slash-command-list">
              {options.map((option, index) => {
                const isActive = index === activeIndex;
                return (
                  <button
                    key={option.id}
                    ref={isActive ? activeItemRef : null}
                    type="button"
                    className={`slash-command-item ${isActive ? "active" : ""}`}
                    style={isActive ? { background: 'rgba(0,0,0,0.08)'} : undefined}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      onSelect(option);
                    }}
                    onMouseEnter={() => onHover(index)}
                  >
                    <TerminalSquare className="slash-command-icon" size={14} />
                    <span className="slash-command-text">
                      <span className="slash-command-name">
                        /{option.name}
                      </span>
                      {option.aliases.length > 0 && (
                        <span className="slash-command-aliases">
                          ({option.aliases.join(", ")})
                        </span>
                      )}
                      <span className="slash-command-desc">
                        {option.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        ) : (
          <div className="slash-command-empty">
            {query
              ? `No commands match "/${query}".`
              : "No commands available."}
          </div>
        )}
      </div>
    </div>
  );
}

export default SlashCommandMenu;
