/**
 * 全局 Loading 遮罩
 */
import { createPortal } from "react-dom";
import octopusLogo from "../../assets/octopus-logo.png";

export default function GlobalLoadingOverlay() {
  const overlayContent = (
    <div
      className="global-loading-overlay"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: "100vw",
        height: "100vh",
        background: "var(--bg, #1a1a1a)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2147483647,
        gap: "32px",
      }}
    >
      {/* Logo */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        <img
          src={octopusLogo}
          alt="Octopus"
          style={{ width: 64, height: 80, objectFit: "contain" }}
        />
        <span
          style={{
            fontSize: "32px",
            fontWeight: 700,
            color: "var(--text, #e0e0e0)",
            fontFamily: "system-ui, -apple-system, sans-serif",
            letterSpacing: "2px",
          }}
        >
          OCTOPUS
        </span>
      </div>

      {/* 小球掉落动画 */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          gap: "12px",
          height: "80px",
        }}
      >
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="bouncing-ball"
            style={{
              width: "16px",
              height: "16px",
              backgroundColor: "#ec5e37ff",
              borderRadius: "50%",
              animation: `bounce 0.6s ease-in-out infinite`,
              animationDelay: `${i * 0.12}s`,
            }}
          />
        ))}
      </div>

      {/* 小球动画样式 */}
      <style>{`
        @keyframes bounce {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-50px);
          }
        }
      `}</style>
    </div>
  );

  return createPortal(overlayContent, document.body);
}
