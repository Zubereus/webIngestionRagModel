import React, { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { addPage } from "../../api/client";
import type { Page } from "../../api/types";
import { strings } from "../../strings";

interface AddLinkInputProps {
  onPageAdded: (page: Page) => void;
  onDuplicatePage: (page: Page) => void;
  selectedCollection: string;
}

export const AddLinkInput: React.FC<AddLinkInputProps> = ({
  onPageAdded,
  onDuplicatePage,
  selectedCollection,
}) => {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [requestError, setRequestError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastSubmittedUrl, setLastSubmittedUrl] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const submitAddress = async (address: string) => {
    const trimmedAddress = address.trim();
    if (!trimmedAddress) {
      setValidationError(strings.pageAddressRequired);
      setNotice("");
      return;
    }

    let parsedAddress: URL;
    try {
      parsedAddress = new URL(trimmedAddress);
    } catch {
      setValidationError(strings.addressMustBeHttp);
      setNotice("");
      return;
    }
    if (parsedAddress.protocol !== "http:" && parsedAddress.protocol !== "https:") {
      setValidationError(strings.addressMustBeHttp);
      setNotice("");
      return;
    }

    setValidationError("");
    setRequestError("");
    setNotice("");
    setLastSubmittedUrl(trimmedAddress);
    setLoading(true);

    try {
      const page = await addPage(trimmedAddress, selectedCollection);
      if (page.duplicate) {
        onDuplicatePage(page);
        setNotice(strings.alreadySaved);
      } else {
        onPageAdded(page);
        setNotice(strings.pageAdded);
      }
      setValue("");
    } catch (error: unknown) {
      setRequestError(error instanceof Error ? error.message : strings.addressMustBeHttp);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submitAddress(value);
  };

  return (
    <form className="space-y-2" onSubmit={handleSubmit} noValidate>
      <label htmlFor="library-page-address" className="sr-only">
        {strings.addPageAddressLabel}
      </label>
      <div className="flex items-stretch gap-2">
        <input
          ref={inputRef}
          id="library-page-address"
          type="text"
          inputMode="url"
          autoComplete="url"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setValidationError("");
            setRequestError("");
            setNotice("");
          }}
          disabled={loading}
          placeholder={strings.addPageAddressPlaceholder}
          aria-invalid={Boolean(validationError || requestError)}
          aria-describedby={
            validationError || requestError ? "library-address-error" : undefined
          }
          className="min-h-10 min-w-0 flex-1 rounded-ctrl border border-line bg-surface px-3 text-sm text-text placeholder:text-text-muted focus-visible:border-accent disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading}
          className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-ctrl bg-accent px-3 text-sm font-medium text-accent-fg hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {strings.addPage}
        </button>
      </div>

      {validationError && (
        <p id="library-address-error" className="text-xs text-err" role="alert">
          {validationError}
        </p>
      )}
      {requestError && (
        <div className="flex items-center justify-between gap-2" role="alert">
          <p id="library-address-error" className="flex items-center gap-1.5 text-xs text-err">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {requestError}
          </p>
          {lastSubmittedUrl && (
            <button
              type="button"
              onClick={() => void submitAddress(lastSubmittedUrl)}
              disabled={loading}
              className="min-h-8 shrink-0 rounded px-2 text-xs font-medium text-accent hover:bg-accent-soft disabled:opacity-60"
            >
              {strings.pageRetry}
            </button>
          )}
        </div>
      )}
      {notice && (
        <p
          className={`text-xs ${notice === strings.alreadySaved ? "text-text-muted" : "text-ok"}`}
          role="status"
        >
          {notice}
        </p>
      )}
    </form>
  );
};
