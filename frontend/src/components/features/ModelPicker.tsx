"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Lock } from "lucide-react";
import { getLlmConfig, getModels } from "@/services/api";
import type { ApiLlmConfig, ApiModels } from "@/types/api";

export type ModelSelection = { provider: string; model: string };

const PROVIDER_LABELS: Record<string, string> = {
  gemini: "Google Gemini",
  openai: "OpenAI",
  ollama: "Ollama (Local)",
};

function isConfigured(config: ApiLlmConfig | null, provider: string): boolean {
  if (!config) return false;
  if (provider === "gemini") return !!config.gemini?.hasKey;
  if (provider === "openai") return !!config.openai?.hasKey;
  if (provider === "ollama")
    return !!(config.ollama?.committedEndpoint || config.ollama?.endpoint);
  return false;
}

type Group = {
  provider: string;
  label: string;
  configured: boolean;
  options: { value: string; label: string }[];
};

export type ModelPickerProps = {
  value: ModelSelection;
  onChange: (value: ModelSelection) => void;
  /** Chamado quando terminamos de carregar, informando se há algum modelo utilizável. */
  onReady?: (hasUsableModel: boolean) => void;
};

/**
 * Lista de modelos agrupada por provider. Os modelos de provedores sem
 * credencial configurada aparecem, mas ficam desabilitados (não selecionáveis) —
 * o sistema já sabe o que está setado a partir de getLlmConfig().
 */
export default function ModelPicker({ value, onChange, onReady }: ModelPickerProps) {
  const [models, setModels] = useState<ApiModels | null>(null);
  const [config, setConfig] = useState<ApiLlmConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([getModels(), getLlmConfig()])
      .then(([m, c]) => {
        if (!alive) return;
        setModels(m);
        setConfig(c);
      })
      .catch(() => alive && setError("Falha ao carregar modelos/configuração."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const groups = useMemo<Group[]>(() => {
    if (!models) return [];
    return Object.entries(models).map(([provider, opts]) => ({
      provider,
      label: PROVIDER_LABELS[provider] ?? provider,
      configured: isConfigured(config, provider),
      options: (opts ?? []).map((o) => ({ value: o.value, label: o.label })),
    }));
  }, [models, config]);

  // Seleção padrão assim que carrega: usa o último salvo se o provider estiver
  // configurado; senão, o primeiro modelo de um provider configurado.
  useEffect(() => {
    if (loading || !models) return;
    const anyConfigured = groups.some((g) => g.configured && g.options.length > 0);
    onReady?.(anyConfigured);

    // Se o valor atual já é válido (provider configurado + modelo existe), mantém.
    const currentGroup = groups.find((g) => g.provider === value.provider);
    const currentValid =
      !!currentGroup &&
      currentGroup.configured &&
      currentGroup.options.some((o) => o.value === value.model);
    if (currentValid) return;

    // Tenta o último salvo.
    const saved = config?.__lastSavedConfig;
    if (saved?.provider) {
      const g = groups.find((x) => x.provider === saved.provider);
      if (g && g.configured) {
        const model =
          g.options.find((o) => o.value === saved.model)?.value ??
          g.options[0]?.value;
        if (model) {
          onChange({ provider: g.provider, model });
          return;
        }
      }
    }

    // Senão, primeiro provider configurado com modelos.
    const first = groups.find((g) => g.configured && g.options.length > 0);
    if (first) {
      onChange({ provider: first.provider, model: first.options[0].value });
    } else {
      onChange({ provider: "", model: "" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, models, config]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-stroke bg-black/30 px-4 py-3 text-sm text-zinc-500">
        <Loader2 className="size-4 animate-spin" strokeWidth={2} />
        Carregando modelos…
      </div>
    );
  }

  if (error) {
    return (
      <p className="rounded-lg border border-rose-900/60 bg-rose-950/30 px-4 py-2.5 text-sm text-rose-400">
        {error}
      </p>
    );
  }

  const anyConfigured = groups.some((g) => g.configured && g.options.length > 0);

  return (
    <div>
      {!anyConfigured ? (
        <p className="mb-2 rounded-lg border border-amber-900/60 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
          Nenhum modelo configurado. Configure uma credencial em{" "}
          <span className="font-semibold">Perfil → LLM Configs</span> para poder
          gerar.
        </p>
      ) : null}

      <div className="max-h-64 overflow-y-auto rounded-lg border border-stroke bg-black/30">
        {groups.map((group) => (
          <div key={group.provider}>
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-stroke/60 bg-[#141416] px-3 py-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
                {group.label}
              </span>
              {group.configured ? (
                <span className="text-[10px] font-medium text-brand">
                  configurado
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[10px] font-medium text-zinc-500">
                  <Lock className="size-3" strokeWidth={2} aria-hidden />
                  não configurado
                </span>
              )}
            </div>

            {group.options.map((opt) => {
              const active =
                group.configured &&
                group.provider === value.provider &&
                opt.value === value.model;
              const disabled = !group.configured;
              return (
                <button
                  key={`${group.provider}:${opt.value}`}
                  type="button"
                  disabled={disabled}
                  onClick={() =>
                    onChange({ provider: group.provider, model: opt.value })
                  }
                  className={`flex w-full items-center justify-between gap-3 border-b border-stroke/40 px-4 py-2 text-left text-sm transition last:border-b-0 ${
                    disabled
                      ? "cursor-not-allowed text-zinc-600"
                      : active
                        ? "bg-brand/10 text-brand"
                        : "text-zinc-300 hover:bg-white/5"
                  }`}
                  title={disabled ? "Provedor sem credencial configurada" : undefined}
                >
                  <span className="font-medium">{opt.label}</span>
                  {active ? (
                    <Check className="size-4 shrink-0" strokeWidth={2} aria-hidden />
                  ) : disabled ? (
                    <Lock className="size-3.5 shrink-0" strokeWidth={2} aria-hidden />
                  ) : null}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
