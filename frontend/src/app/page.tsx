"use client";

import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Upload,
  Video,
  Music,
  Sparkles,
  Download,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type PipelineStep = "idle" | "uploading" | "analyzing" | "prompting" | "generating" | "combining" | "done" | "error";

const STEP_LABELS: Record<PipelineStep, string> = {
  idle: "Ready",
  uploading: "Uploading video...",
  analyzing: "Analyzing video with Google Cloud AI...",
  prompting: "Crafting music prompt with OpenAI...",
  generating: "Generating audio with Suno AI...",
  combining: "Combining video and audio...",
  done: "Complete!",
  error: "Something went wrong",
};

const STEP_PROGRESS: Record<PipelineStep, number> = {
  idle: 0,
  uploading: 10,
  analyzing: 30,
  prompting: 50,
  generating: 70,
  combining: 90,
  done: 100,
  error: 0,
};

export default function Home() {
  const [step, setStep] = useState<PipelineStep>("idle");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoPreview, setVideoPreview] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback((file: File) => {
    if (!file.type.startsWith("video/")) {
      setError("Please select a valid video file");
      return;
    }

    // Check video duration
    const videoElement = document.createElement("video");
    videoElement.preload = "metadata";

    videoElement.onloadedmetadata = () => {
      window.URL.revokeObjectURL(videoElement.src);
      const duration = videoElement.duration;

      if (duration > 60) {
        setError(`Video is too long (${duration.toFixed(1)}s). Maximum allowed duration is 60 seconds.`);
        return;
      }

      setVideoFile(file);
      setVideoPreview(URL.createObjectURL(file));
      setResultUrl(null);
      setError(null);
      setStep("idle");
    };

    videoElement.onerror = () => {
      setError("Unable to read video file");
    };

    videoElement.src = URL.createObjectURL(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleGenerate = async () => {
    if (!videoFile) return;

    setError(null);
    setResultUrl(null);
    setStep("uploading");

    try {
      // Use Server-Sent Events for real-time progress
      const formData = new FormData();
      formData.append("video", videoFile);

      // First, upload the video and start the streaming endpoint
      const uploadResponse = await fetch(`${API_URL}/api/generate-stream`, {
        method: "POST",
        body: formData,
      });

      if (!uploadResponse.ok) {
        if (uploadResponse.status === 429) {
          throw new Error("Rate limit exceeded. You can only process 3 videos per hour. Please try again later.");
        }
        const errorData = await uploadResponse.json().catch(() => null);
        throw new Error(errorData?.detail || `Upload failed: ${uploadResponse.status}`);
      }

      const reader = uploadResponse.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response stream available");
      }

      let buffer = "";

      // Read the SSE stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6));
            console.log("[Frontend] Progress update:", data);

            setStep(data.stage as PipelineStep);
            setStatusMessage(data.message);

            if (data.stage === "error") {
              throw new Error(data.message);
            }

            if (data.stage === "done") {
              // Fetch the completed video
              const filename = data.message.split("File: ")[1];
              const videoResponse = await fetch(`${API_URL}/api/outputs/${filename}`);

              if (!videoResponse.ok) {
                throw new Error("Failed to fetch completed video");
              }

              const blob = await videoResponse.blob();
              const url = URL.createObjectURL(blob);
              setResultUrl(url);
            }
          }
        }
      }
    } catch (err) {
      console.error("[Frontend] Error:", err);
      setStep("error");
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    }
  };

  const handleReset = () => {
    setVideoFile(null);
    setVideoPreview(null);
    setResultUrl(null);
    setError(null);
    setStatusMessage("");
    setStep("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDownload = () => {
    if (!resultUrl) return;
    const a = document.createElement("a");
    a.href = resultUrl;
    a.download = `bruno_${videoFile?.name || "output.mp4"}`;
    a.click();
  };

  const isProcessing = !["idle", "done", "error"].includes(step);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Music className="w-4 h-4 text-primary-foreground" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">Bruno</h1>
          </div>
          <span className="text-sm text-muted-foreground">
            AI-powered audio generation for your videos
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {/* Pipeline Steps Visual */}
        <div className="mb-10">
          <div className="grid grid-cols-4 gap-3">
            {[
              { icon: Video, label: "Analyze Video", desc: "Google Cloud AI" },
              { icon: Sparkles, label: "Craft Prompt", desc: "OpenAI GPT-4o" },
              { icon: Music, label: "Generate Audio", desc: "Suno AI" },
              { icon: CheckCircle2, label: "Combine", desc: "Video + Audio" },
            ].map((item, i) => {
              const stepOrder: PipelineStep[] = ["analyzing", "prompting", "generating", "combining"];
              const isActive = stepOrder.indexOf(step) >= i;
              const isCurrent = stepOrder[i] === step;

              return (
                <div
                  key={i}
                  className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border transition-all duration-500 ease-in-out ${
                    isCurrent
                      ? "border-primary bg-primary/5 shadow-lg shadow-primary/20 scale-105"
                      : isActive
                      ? "border-primary/30 bg-primary/5 opacity-100"
                      : "border-border bg-card opacity-60"
                  }`}
                  style={{
                    animation: isCurrent ? "pulse-glow 2s ease-in-out infinite" : "none",
                  }}
                >
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500 ${
                      isCurrent
                        ? "bg-primary text-primary-foreground animate-pulse"
                        : isActive
                        ? "bg-primary/20 text-primary"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {isCurrent ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : isActive ? (
                      <CheckCircle2 className="w-5 h-5 animate-in fade-in duration-500" />
                    ) : (
                      <item.icon className="w-5 h-5 opacity-50" />
                    )}
                  </div>
                  <div className="text-center transition-all duration-300">
                    <p className={`text-sm font-medium transition-all duration-300 ${
                      isCurrent ? "scale-105" : ""
                    }`}>{item.label}</p>
                    <p className={`text-xs text-muted-foreground transition-opacity duration-300 ${
                      isCurrent ? "opacity-100" : "opacity-70"
                    }`}>{item.desc}</p>
                  </div>
                  {isCurrent && (
                    <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-16 h-1 bg-primary rounded-full animate-pulse" />
                  )}
                </div>
              );
            })}
          </div>
          {statusMessage && isProcessing && (
            <div className="mt-4 text-center animate-in fade-in slide-in-from-bottom-2 duration-300">
              <p className="text-sm text-muted-foreground">{statusMessage}</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upload Section */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Input Video</CardTitle>
              <CardDescription>Upload a video without audio</CardDescription>
            </CardHeader>
            <CardContent>
              {!videoFile ? (
                <div
                  className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all ${
                    isDragging
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50 hover:bg-muted/50"
                  }`}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                  <p className="text-sm font-medium mb-1">
                    Drop your video here or click to browse
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Supports MP4, MOV, AVI, WebM
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="video/*"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileSelect(file);
                    }}
                  />
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-xl overflow-hidden bg-black aspect-video">
                    <video
                      src={videoPreview || undefined}
                      controls
                      muted
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium truncate max-w-[200px]">
                        {videoFile.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {(videoFile.size / (1024 * 1024)).toFixed(1)} MB
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleReset}
                      disabled={isProcessing}
                    >
                      Change
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Output Section */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Output Video</CardTitle>
              <CardDescription>Your video with AI-generated audio</CardDescription>
            </CardHeader>
            <CardContent>
              {resultUrl ? (
                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
                  <div className="rounded-xl overflow-hidden bg-black aspect-video shadow-lg">
                    <video
                      src={resultUrl}
                      controls
                      autoPlay
                      playsInline
                      className="w-full h-full object-contain"
                      onLoadedData={() => console.log("[Video] Loaded successfully")}
                      onError={(e) => {
                        console.error("[Video] Error loading:", e);
                        console.error("[Video] Error details:", (e.target as HTMLVideoElement).error);
                      }}
                    />
                  </div>
                  <Button onClick={handleDownload} className="w-full gap-2 animate-in fade-in duration-500 delay-300">
                    <Download className="w-4 h-4" />
                    Download Video
                  </Button>
                </div>
              ) : (
                <div className="rounded-xl border-2 border-dashed border-border p-10 text-center aspect-video flex flex-col items-center justify-center">
                  {isProcessing ? (
                    <div className="animate-in fade-in duration-500">
                      <div className="relative">
                        <Loader2 className="w-10 h-10 mb-3 text-primary animate-spin mx-auto" />
                        <div className="absolute inset-0 w-10 h-10 mb-3 rounded-full bg-primary/20 blur-xl animate-pulse mx-auto" />
                      </div>
                      <p className="text-sm font-medium mb-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        {STEP_LABELS[step]}
                      </p>
                      <Progress
                        value={STEP_PROGRESS[step]}
                        className="w-full max-w-[200px] transition-all duration-700 ease-out"
                      />
                      <p className="text-xs text-muted-foreground mt-2 animate-pulse">
                        This may take a few minutes
                      </p>
                    </div>
                  ) : error ? (
                    <div className="animate-in fade-in zoom-in duration-300">
                      <XCircle className="w-10 h-10 mb-3 text-destructive mx-auto" />
                      <p className="text-sm font-medium text-destructive mb-1">Error</p>
                      <p className="text-xs text-muted-foreground">{error}</p>
                    </div>
                  ) : (
                    <div className="animate-in fade-in duration-500">
                      <Music className="w-10 h-10 mb-3 text-muted-foreground mx-auto opacity-50" />
                      <p className="text-sm text-muted-foreground">
                        Output will appear here
                      </p>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Generate Button */}
        <div className="mt-6 flex justify-center">
          <Button
            size="lg"
            onClick={handleGenerate}
            disabled={!videoFile || isProcessing}
            className="gap-2 px-8"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Generate Audio
              </>
            )}
          </Button>
        </div>
      </main>
    </div>
  );
}
