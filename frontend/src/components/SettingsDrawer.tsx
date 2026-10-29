import React, { useEffect, useState } from "react";
import {
  X,
  Moon,
  Sun,
  Monitor,
  Download,
  Trash2,
  Check,
  AlertTriangle,
} from "lucide-react";
import {
  getApiBaseUrl,
  setApiBaseUrl,
  isMockMode,
  setMockMode,
  DEFAULT_API_URL,
  fetchGenerationModels,
  getSelectedModel,
} from "../api/client";
import type { GenerationModel } from "../api/types";
import type { Theme } from "../hooks/useTheme";

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
  topK: number;
  onTopKChange: (k: number) => void;
  onClearLibrary: () => Promise<void>;
  onRefresh: () => void;
  selectedModel: string | null;
  onModelChange: (model: string) => void;
}

export const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  isOpen,
  onClose,
  theme,
  onThemeChange,
  topK,
  onTopKChange,
  onClearLibrary,
  onRefresh,
  selectedModel,
  onModelChange,
}) => {
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());
  const [mockActive, setMockActive] = useState(isMockMode());
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [confirmInput, setConfirmInput] = useState("");
  const [urlSaved, setUrlSaved] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);
  const [models, setModels] = useState<GenerationModel[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [modelsError, setModelsError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    void fetchGenerationModels()
      .then((result) => {
        if (!active) return;
        setModelsError(null);
        setModels(result.models);
        setDefaultModel(result.default_model);
        const savedModel = getSelectedModel();
        const selected = result.models.find(
          (model) => model.id === (savedModel || result.default_model) && model.available,
        ) ?? result.models.find((model) => model.available);
        if (selected && selected.id !== savedModel) {
          onModelChange(selected.id);
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setModelsError(
          error instanceof Error ? error.message : "Could not load available models.",
        );
      });
    return () => {
      active = false;
    };
  }, [isOpen, onModelChange]);

  if (!isOpen) return null;

  const handleSaveUrl = () => {
    setApiBaseUrl(apiUrl);
    setUrlSaved(true);
    setTimeout(() => setUrlSaved(false), 2000);
  };

  const handleToggleMock = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.checked;
    setMockActive(val);
    setMockMode(val);
    onRefresh();
  };

  const handleClearSubmit = async () => {
    if (confirmInput.trim().toLowerCase() === "clear") {
      setClearError(null);
      try {
        await onClearLibrary();
        setShowClearConfirm(false);
        setConfirmInput("");
      } catch (error) {
        setClearError(
          error instanceof Error ? error.message : "The library could not be cleared.",
        );
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity">
      <div className="w-full max-w-sm h-full bg-surface border-l border-line shadow-2xl flex flex-col p-5 space-y-6 overflow-y-auto">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-line pb-3">
          <h2 className="text-lg font-semibold text-text">Settings</h2>
          <button
            onClick={onClose}
            className="p-1 rounded text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
            aria-label="Close settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Theme Settings */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-text-muted">
            Appearance
          </label>
          <div className="grid grid-cols-3 gap-2">
            {([
              { id: "light", label: "Light", icon: Sun },
              { id: "dark", label: "Dark", icon: Moon },
              { id: "system", label: "System", icon: Monitor },
            ] as const).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => onThemeChange(id)}
                className={`flex flex-col items-center justify-center p-2.5 rounded-ctrl border text-xs gap-1.5 transition-colors ${
                  theme === id
                    ? "border-accent bg-accent-soft text-accent font-medium"
                    : "border-line bg-surface-2 text-text-muted hover:text-text"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Retrieval Top-K Slider */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-medium text-text-muted">
              Top-K Passages
            </span>
            <span className="font-mono text-accent font-medium">{topK}</span>
          </div>
          <input
            type="range"
            min={1}
            max={10}
            value={topK}
            onChange={(e) => onTopKChange(parseInt(e.target.value, 10))}
            className="w-full accent-accent cursor-pointer"
          />
          <p className="text-[11px] text-text-muted">
            Number of supporting passages retrieved for each question.
          </p>
        </div>

        <div className="space-y-2 border-t border-line pt-4">
          <label htmlFor="generation-model" className="text-sm font-medium text-text-muted">
            Generation model
          </label>
          <select
            id="generation-model"
            value={selectedModel ?? defaultModel}
            onChange={(event) => onModelChange(event.target.value)}
            disabled={models.length === 0}
            className="w-full rounded-ctrl border border-line bg-bg p-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            {models.map((model) => (
              <option key={model.id} value={model.id} disabled={!model.available}>
                {model.label}{!model.available ? " · API key required" : ""}
              </option>
            ))}
          </select>
          {modelsError ? (
            <p role="alert" className="text-xs text-err">{modelsError}</p>
          ) : (
            <p className="text-[11px] text-text-muted">
              Choose a local Ollama model or Gemini. Set GEMINI_API_KEY on the backend to enable Gemini.
            </p>
          )}
        </div>

        {/* Backend & Mock Mode Settings */}
        <div className="space-y-3 pt-2 border-t border-line">
          <label className="text-sm font-medium text-text-muted">
            Backend API Connection
          </label>

          <div className="flex gap-2">
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder={DEFAULT_API_URL}
              className="flex-1 p-2 text-xs font-mono bg-bg border border-line rounded-ctrl text-text focus:outline-none focus:border-accent"
            />
            <button
              onClick={handleSaveUrl}
              className="px-3 py-1.5 text-xs rounded-ctrl bg-surface-2 hover:bg-line border border-line text-text font-medium transition-colors"
            >
              {urlSaved ? <Check className="w-3.5 h-3.5 text-ok" /> : "Save"}
            </button>
          </div>

          {import.meta.env.DEV && (
            <label className="flex items-center gap-2 text-xs text-text cursor-pointer select-none">
              <input
                type="checkbox"
                checked={mockActive}
                onChange={handleToggleMock}
                className="rounded border-line text-accent accent-accent"
              />
              <span>Enable Mock Mode (development only)</span>
            </label>
          )}
        </div>

        {/* Dataset Export & Library Reset */}
        <div className="space-y-3 pt-4 border-t border-line">
          <label className="text-sm font-medium text-text-muted">
            Data Management
          </label>

          <a
            href={`${apiUrl}/api/export`}
            download
            className="w-full flex items-center justify-center gap-2 p-2 text-xs rounded-ctrl bg-surface-2 hover:bg-line border border-line text-text transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Chunks Dataset (JSONL)</span>
          </a>

          {!showClearConfirm ? (
            <button
              onClick={() => setShowClearConfirm(true)}
              className="w-full flex items-center justify-center gap-2 p-2 text-xs rounded-ctrl border border-err/40 text-err hover:bg-err/10 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Saved Library</span>
            </button>
          ) : (
            <div className="p-3 bg-err/10 border border-err/30 rounded-ctrl space-y-2 text-xs">
              <div className="flex items-center gap-1.5 text-err font-medium">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Type "clear" to confirm:</span>
              </div>
              <input
                type="text"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                placeholder="clear"
                className="w-full p-1.5 text-xs bg-bg border border-err rounded text-text font-mono"
              />
              {clearError && (
                <p role="alert" className="text-err">
                  {clearError}
                </p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={handleClearSubmit}
                  disabled={confirmInput.trim().toLowerCase() !== "clear"}
                  className="flex-1 py-1 rounded bg-err text-bg font-medium disabled:opacity-40"
                >
                  Confirm Delete
                </button>
                <button
                  onClick={() => setShowClearConfirm(false)}
                  className="px-2 py-1 rounded bg-surface-2 text-text"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
