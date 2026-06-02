import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const WHITESPACE_REGEX = /\s/;
const NON_WHITESPACE_START = /^\S/;

/**
 * Detect if the cursor is inside a slash command at the beginning of input or line.
 * Slash commands are only valid at the start of input or after a newline.
 */
const detectSlash = (text, caret) => {
  const safeCaret = Math.max(0, Math.min(text.length, caret ?? text.length));
  const upToCaret = text.slice(0, safeCaret);

  const slashIndex = upToCaret.lastIndexOf("/");
  if (slashIndex === -1) {
    return null;
  }

  if (slashIndex > 0) {
    const prevChar = upToCaret[slashIndex - 1];
    if (prevChar !== "\n") {
      return null;
    }
  }

  const query = upToCaret.slice(slashIndex + 1);

  if (WHITESPACE_REGEX.test(query)) {
    return null;
  }

  return {
    start: slashIndex,
    end: safeCaret,
    query,
  };
};

const isSameRange = (a, b) =>
  a?.start === b?.start && a?.end === b?.end && a?.query === b?.query;

const toSlashOptions = (commands) =>
  commands.map((cmd) => ({
    id: `slash-${cmd.name}`,
    name: cmd.name,
    description: cmd.description,
    aliases: cmd.aliases || [],
    insertValue: `/${cmd.name}`,
    action: cmd.action,
  }));

const filterOptions = (options, query) => {
  if (!options.length) {
    return [];
  }

  const normalizedQuery = query.trim().toLowerCase();
  if (normalizedQuery.length === 0) {
    return options;
  }

  return options.filter((option) => {
    const matchesName = option.name.toLowerCase().includes(normalizedQuery);
    const matchesAlias = option.aliases.some((alias) =>
      alias.toLowerCase().includes(normalizedQuery),
    );
    return matchesName || matchesAlias;
  });
};

export const useSlashCommands = ({ text, setText, textareaRef, commands }) => {
  const [range, setRange] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const isSelectingRef = useRef(false);

  const allOptions = useMemo(() => toSlashOptions(commands), [commands]);

  const options = useMemo(
    () => filterOptions(allOptions, range?.query ?? ""),
    [allOptions, range?.query],
  );

  useEffect(() => {
    if (activeIndex >= options.length) {
      setActiveIndex(options.length === 0 ? 0 : options.length - 1);
    }
  }, [activeIndex, options.length]);

  const prevRangeRef = useRef(null);
  useEffect(() => {
    if (range !== null && prevRangeRef.current === null) {
      setActiveIndex(0);
    }
    prevRangeRef.current = range;
  }, [range]);

  useEffect(() => {
    if (isSelectingRef.current) {
      return;
    }
    const caret = textareaRef.current?.selectionStart ?? text.length;
    const next = detectSlash(text, caret);
    setRange((previous) => (isSameRange(previous, next) ? previous : next));
  }, [text, textareaRef]);

  const handleTextChange = useCallback(
    (value, caret) => {
      if (isSelectingRef.current) {
        return;
      }
      setRange(detectSlash(value, caret));
    },
    [],
  );

  const handleCaretChange = useCallback(
    (caret) => {
      if (isSelectingRef.current) {
        return;
      }
      const next = detectSlash(text, caret);
      setRange((previous) => (isSameRange(previous, next) ? previous : next));
    },
    [text],
  );

  const closeMenu = useCallback(() => {
    setRange(null);
  }, []);

  const selectOption = useCallback(
    (option) => {
      if (!range) {
        return;
      }
      const target = option ?? options[activeIndex];
      if (!target) {
        return;
      }

      const before = text.slice(0, range.start);
      const after = text.slice(range.end);
      const needsSpace =
        after.length === 0 || NON_WHITESPACE_START.test(after) ? " " : "";
      const nextValue = `${before}${target.insertValue}${needsSpace}${after}`;
      const nextCaret =
        before.length + target.insertValue.length + needsSpace.length;

      isSelectingRef.current = true;

      const node = textareaRef.current;
      if (node) {
        node.blur();
      }

      setRange(null);
      setActiveIndex(0);

      requestAnimationFrame(() => {
        setText(nextValue);

        requestAnimationFrame(() => {
          try {
            const currentNode = textareaRef.current;
            if (currentNode) {
              currentNode.focus();
              currentNode.setSelectionRange(nextCaret, nextCaret);
            }
          } finally {
            setTimeout(() => {
              isSelectingRef.current = false;
            }, 0);
          }
        });
      });

      // If the command has an immediate action, trigger it
      if (target.action) {
        // Defer so the text replacement completes first
        setTimeout(() => {
          target.action();
        }, 50);
      }
    },
    [range, options, activeIndex, text, setText, textareaRef],
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (!range) {
        return;
      }

      const isArrowDown = event.key === "ArrowDown" || event.key === "Down" || event.keyCode === 40;
      const isArrowUp = event.key === "ArrowUp" || event.key === "Up" || event.keyCode === 38;
      const isEnter = event.key === "Enter" || event.keyCode === 13;
      const isTab = event.key === "Tab" || event.keyCode === 9;
      const isEscape = event.key === "Escape" || event.key === "Esc" || event.keyCode === 27;

      if (isArrowDown) {
        if (options.length === 0) {
          return;
        }
        event.preventDefault();
        setActiveIndex((previous) => (previous + 1) % options.length);
        return;
      }

      if (isArrowUp) {
        if (options.length === 0) {
          return;
        }
        event.preventDefault();
        setActiveIndex((previous) =>
          previous - 1 < 0 ? options.length - 1 : (previous - 1) % options.length,
        );
        return;
      }

      if (isEnter || isTab) {
        if (options.length === 0) {
          return;
        }
        event.preventDefault();
        selectOption();
        return;
      }

      if (isEscape) {
        event.preventDefault();
        closeMenu();
      }
    },
    [range, options, selectOption, closeMenu],
  );

  return {
    isOpen: Boolean(range),
    query: range?.query ?? "",
    options,
    activeIndex,
    setActiveIndex,
    handleTextChange,
    handleCaretChange,
    handleKeyDown,
    selectOption,
    closeMenu,
  };
};
