"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, KeyRound, LoaderCircle, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  checkOpenAIKey,
  createOpenAIKey,
  deleteOpenAIKey,
  fetchOpenAIKeys,
  type OpenAIKeyItem,
} from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

function statusMeta(status: string): { label: string; variant: "success" | "warning" | "danger" | "secondary" | "info" } {
  switch (status) {
    case "ok":
      return { label: "可用", variant: "success" };
    case "invalid":
      return { label: "无效", variant: "danger" };
    case "rate_limited":
      return { label: "限流", variant: "warning" };
    case "forbidden":
      return { label: "无权限", variant: "danger" };
    case "error":
      return { label: "检测失败", variant: "danger" };
    case "unchecked":
      return { label: "未检测", variant: "secondary" };
    default:
      return { label: status || "未知", variant: "info" };
  }
}

function OpenAIKeyManager() {
  const [items, setItems] = useState<OpenAIKeyItem[]>([]);
  const [name, setName] = useState("默认项目");
  const [secret, setSecret] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const stats = useMemo(() => {
    const ok = items.filter((item) => item.status === "ok").length;
    const failed = items.filter((item) => ["invalid", "forbidden", "rate_limited", "error"].includes(item.status)).length;
    return { total: items.length, ok, failed };
  }, [items]);

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await fetchOpenAIKeys();
      setItems(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载 API Key 失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async () => {
    const normalizedSecret = secret.trim();
    if (!normalizedSecret) {
      toast.error("请输入 OpenAI API Key");
      return;
    }
    setIsCreating(true);
    try {
      const data = await createOpenAIKey(name.trim() || "默认项目", normalizedSecret, true);
      setItems(data.items);
      setSecret("");
      toast.success(data.item.status === "ok" ? "API Key 已添加并检测可用" : "API Key 已添加，请查看检测结果");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "添加 API Key 失败");
    } finally {
      setIsCreating(false);
    }
  };

  const handleCheck = async (item: OpenAIKeyItem) => {
    setBusyId(item.id);
    try {
      const data = await checkOpenAIKey(item.id);
      setItems(data.items);
      toast.success(data.item.status === "ok" ? "检测通过" : "检测完成，但 Key 不可用");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "检测失败");
    } finally {
      setBusyId("");
    }
  };

  const handleDelete = async (item: OpenAIKeyItem) => {
    setBusyId(item.id);
    try {
      const data = await deleteOpenAIKey(item.id);
      setItems(data.items);
      toast.success("API Key 已删除");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除失败");
    } finally {
      setBusyId("");
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Official API Keys</div>
          <h1 className="text-2xl font-semibold tracking-tight">OpenAI API Key 管理</h1>
          <p className="max-w-3xl text-sm text-stone-500">
            这里走官方 OpenAI API Key，不再研究自动注册链路。检测只调用只读的 <code className="rounded bg-stone-100 px-1">/v1/models</code>。
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-right">
          {[
            ["总数", stats.total],
            ["可用", stats.ok],
            ["异常", stats.failed],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-stone-200 bg-white/75 px-4 py-2">
              <div className="text-xs text-stone-400">{label}</div>
              <div className="text-lg font-semibold text-stone-900">{value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white/80 p-4 shadow-sm">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-stone-950 text-white">
            <KeyRound className="size-5" />
          </div>
          <div>
            <h2 className="font-semibold text-stone-900">添加官方 API Key</h2>
            <p className="text-sm text-stone-500">完整 Key 只在后端保存，前端列表只显示脱敏片段。</p>
          </div>
        </div>
        <div className="grid gap-3 lg:grid-cols-[220px_1fr_auto]">
          <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="名称，例如 production" />
          <Input
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
            placeholder="sk-proj-..."
            type="password"
            autoComplete="off"
          />
          <Button className="h-11 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800" onClick={() => void handleCreate()} disabled={isCreating}>
            {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
            添加并检测
          </Button>
        </div>
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>这是最小可看版：先做 Key 存储和可用性检测，暂不接管现有图片/聊天调用链。</span>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white/80 shadow-sm">
        <div className="flex items-center justify-between border-b border-stone-100 px-4 py-3">
          <div>
            <h2 className="font-semibold text-stone-900">Key 列表</h2>
            <p className="text-sm text-stone-500">检测结果来自官方模型列表接口。</p>
          </div>
          <Button variant="outline" className="rounded-xl" onClick={() => void load()}>
            <RefreshCw className="size-4" />
            刷新
          </Button>
        </div>
        {items.length === 0 ? (
          <div className="p-10 text-center text-sm text-stone-500">还没有 API Key。先添加一个。</div>
        ) : (
          <div className="divide-y divide-stone-100">
            {items.map((item) => {
              const meta = statusMeta(item.status);
              const isBusy = busyId === item.id;
              return (
                <article key={item.id} className="grid gap-3 px-4 py-4 lg:grid-cols-[1fr_auto] lg:items-center">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-stone-900">{item.name}</h3>
                      <Badge variant={meta.variant} className="rounded-md">
                        {meta.label}
                      </Badge>
                      <span className="rounded-md bg-stone-100 px-2 py-1 font-mono text-xs text-stone-500">{item.key_hint}</span>
                    </div>
                    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-stone-500">
                      <span>HTTP: {item.http_status ?? "-"}</span>
                      <span>模型数: {item.models_count || 0}</span>
                      <span>上次检测: {item.last_checked_at ? new Date(item.last_checked_at).toLocaleString() : "未检测"}</span>
                    </div>
                    {item.sample_models?.length ? (
                      <div className="flex flex-wrap gap-1">
                        {item.sample_models.slice(0, 8).map((model) => (
                          <span key={model} className="rounded bg-stone-100 px-2 py-1 font-mono text-[11px] text-stone-600">
                            {model}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {item.last_error ? <p className="text-xs text-rose-600">{item.last_error}</p> : null}
                  </div>
                  <div className="flex gap-2 lg:justify-end">
                    <Button variant="outline" className="rounded-xl" onClick={() => void handleCheck(item)} disabled={isBusy}>
                      {isBusy ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                      检测
                    </Button>
                    <Button variant="outline" className="rounded-xl text-rose-600 hover:bg-rose-50 hover:text-rose-700" onClick={() => void handleDelete(item)} disabled={isBusy}>
                      <Trash2 className="size-4" />
                      删除
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

export default function RegisterPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);

  if (isCheckingAuth || !session || session.role !== "admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <OpenAIKeyManager />;
}
