import { useEffect, useState } from "react";
import { CheckCircle2, Clock, Download, X } from "lucide-react";
import { getExecutionStatus } from "./api";
import { getUiText } from "./i18n";

function ServiceExecutionFlow({ execution, language, onClose }) {
  const [state, setState] = useState(execution);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [showFinalResult, setShowFinalResult] = useState(false);

  const ui = getUiText(language);

  useEffect(() => {
    if (!state || state.status === "completed") {
      return;
    }

    const interval = window.setInterval(async () => {
      setIsTransitioning(true);
      try {
        const updated = await getExecutionStatus(state.execution_id);
        setState(updated);
        if (updated.status === "completed") {
          setShowFinalResult(true);
        }
      } catch {
        console.error("Failed to get execution status");
      } finally {
        setIsTransitioning(false);
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [state]);

  if (!state) {
    return null;
  }

  const stages = state.stages || [];
  const completedCount = stages.filter((s) => s.status === "done").length;
  const progressPercent = Math.round((completedCount / Math.max(stages.length, 1)) * 100);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-white/15 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <h2 className="font-display text-2xl font-bold text-slate-900">{state.service_name}</h2>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-6 p-6">
          {!showFinalResult ? (
            <>
              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-slate-700">Progress</span>
                  <span className="text-slate-600">{progressPercent}%</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full bg-gradient-to-r from-green-400 to-blue-500 transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>

              {/* Queue Info */}
              {state.queue_info && state.queue_info.position && (
                <div className="rounded-2xl border-2 border-amber-200 bg-amber-50 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <Clock className="h-5 w-5 text-amber-600" />
                    <span className="font-semibold text-amber-900">Queue Information</span>
                  </div>
                  <p className="text-sm text-amber-800">
                    <strong>Your position:</strong> #{state.queue_info.position}
                  </p>
                  <p className="text-sm text-amber-800">
                    <strong>Estimated time:</strong> {state.queue_info.estimated_time}
                  </p>
                </div>
              )}

              {/* Stage Timeline */}
              <div className="space-y-3">
                {stages.map((stage, index) => {
                  const isDone = stage.status === "done";
                  const isCurrent = stage.status === "current";
                  const isPending = stage.status === "pending";

                  return (
                    <div key={`${stage.stage}-${index}`} className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div
                          className={`inline-flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-500 ${
                            isDone
                              ? "border-green-500 bg-green-100 text-green-700"
                              : isCurrent
                                ? "border-blue-500 bg-blue-100 text-blue-700"
                                : "border-slate-300 bg-slate-100 text-slate-400"
                          } ${isCurrent && isTransitioning ? "scale-110" : ""}`}
                        >
                          {isDone ? (
                            <CheckCircle2 className="h-5 w-5" />
                          ) : (
                            <span className="text-sm font-bold">{index + 1}</span>
                          )}
                        </div>
                        {index < stages.length - 1 && (
                          <div
                            className={`mt-1 h-8 w-1 rounded-full transition-all duration-500 ${
                              isDone ? "bg-green-400" : "bg-slate-300"
                            }`}
                          />
                        )}
                      </div>

                      <div className="flex-1 py-1">
                        <p
                          className={`font-semibold ${
                            isCurrent
                              ? "text-blue-700"
                              : isDone
                                ? "text-green-700"
                                : "text-slate-500"
                          }`}
                        >
                          {stage.stage}
                        </p>
                        {isCurrent && (
                          <p className="text-xs text-blue-600">
                            {isTransitioning ? "Updating..." : "Processing..."}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {state.status === "in_progress" && (
                <p className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-center text-sm font-semibold text-blue-900">
                  Service is processing automatically...
                </p>
              )}
            </>
          ) : (
            /* Final Result Screen */
            <div className="space-y-4 text-center">
              <div className="mx-auto inline-flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>

              {state.final_result && (
                <>
                  <div>
                    <h3 className="font-display text-2xl font-bold text-slate-900">
                      {state.final_result.title}
                    </h3>
                    <p className="mt-2 text-slate-700">{state.final_result.message}</p>
                  </div>

                  {state.final_result.type === "certificate" && (
                    <a
                      href={state.final_result.download_url}
                      className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
                    >
                      <Download className="h-4 w-4" />
                      Download Certificate
                    </a>
                  )}

                  {(state.final_result.type === "application" || state.final_result.type === "approval") && (
                    <div
                      className={`rounded-xl p-4 ${
                        state.final_result.decision === "rejected"
                          ? "border border-rose-200 bg-rose-50"
                          : "border border-green-200 bg-green-50"
                      }`}
                    >
                      <p
                        className={`text-sm font-semibold ${
                          state.final_result.decision === "rejected" ? "text-rose-900" : "text-green-900"
                        }`}
                      >
                        Status: {state.final_result.decision === "rejected" ? "Rejected" : "Approved"}
                      </p>
                      {state.final_result.reference_number && (
                        <p
                          className={`mt-1 text-sm ${
                            state.final_result.decision === "rejected" ? "text-rose-800" : "text-green-800"
                          }`}
                        >
                          Reference: {state.final_result.reference_number}
                        </p>
                      )}
                    </div>
                  )}

                  {state.final_result.type === "queue_turn" && (
                    <div className="rounded-xl border border-purple-200 bg-purple-50 p-4">
                      <p className="text-sm font-semibold text-purple-900">
                        {state.final_result.next_steps}
                      </p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-slate-200 p-4">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default ServiceExecutionFlow;
