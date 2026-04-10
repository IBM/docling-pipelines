import reflex as rx
from chat_with_file_ingestion.states.file_state import FileUploadState, LogPollerState


def _status_badge() -> rx.Component:
    """Color-coded status badge shown in the log tearsheet header area."""
    return rx.cond(
        FileUploadState.processing_status != "",
        rx.el.div(
            rx.cond(
                FileUploadState.processing_failed,
                rx.el.div(
                    rx.icon(
                        "circle-x", class_name="h-3.5 w-3.5 text-red-400 flex-shrink-0"
                    ),
                    rx.el.p(
                        FileUploadState.processing_status,
                        class_name="text-xs text-red-300 font-medium",
                    ),
                    class_name="flex items-center gap-2",
                ),
                rx.cond(
                    FileUploadState.is_processing,
                    rx.el.div(
                        rx.icon(
                            "loader",
                            class_name="h-3.5 w-3.5 text-amber-400 animate-spin flex-shrink-0",
                        ),
                        rx.el.p(
                            FileUploadState.processing_status,
                            class_name="text-xs text-amber-300 font-medium",
                        ),
                        class_name="flex items-center gap-2",
                    ),
                    rx.el.div(
                        rx.icon(
                            "circle-check",
                            class_name="h-3.5 w-3.5 text-green-400 flex-shrink-0",
                        ),
                        rx.el.p(
                            FileUploadState.processing_status,
                            class_name="text-xs text-green-300 font-medium",
                        ),
                        class_name="flex items-center gap-2",
                    ),
                ),
            ),
            class_name="px-4 py-2 bg-gray-800 border-b border-gray-700 flex-shrink-0",
        ),
    )


def _log_line(line: str) -> rx.Component:
    """
    Render a single log line with color coding based on level keyword.
    Uses rx.cond chains since rx.match requires exact equality.
    Log format from Python logging: '2024-01-01 12:00:00 [LEVEL] name: message'
    """
    return rx.el.p(
        line,
        class_name=rx.cond(
            line.contains(" - ERROR - ")
            | line.contains(" ERROR ")
            | line.contains("ERROR:")
            | line.contains("Failed to")
            | line.contains("Traceback")
            | line.contains("Exception"),
            "text-[11px] font-mono text-red-400 leading-relaxed whitespace-pre-wrap break-all py-0.5",
            rx.cond(
                line.contains(" - WARNING - ")
                | line.contains(" WARN ")
                | line.contains("WARNING:")
                | line.contains("Warning:"),
                "text-[11px] font-mono text-amber-400 leading-relaxed whitespace-pre-wrap break-all py-0.5",
                rx.cond(
                    line.contains(" - INFO - ")
                    | line.contains(" INFO ")
                    | line.contains("INFO:"),
                    "text-[11px] font-mono text-green-400 leading-relaxed whitespace-pre-wrap break-all py-0.5",
                    "text-[11px] font-mono text-gray-400 leading-relaxed whitespace-pre-wrap break-all py-0.5",
                ),
            ),
        ),
    )


def file_status_icon(status: str) -> rx.Component:
    return rx.match(
        status,
        (
            "uploading",
            rx.icon("refresh-cw", class_name="h-4 w-4 text-blue-500 animate-spin"),
        ),
        (
            "processing",
            rx.icon("cpu", class_name="h-4 w-4 text-amber-500 animate-pulse"),
        ),
        ("complete", rx.icon("languages", class_name="h-4 w-4 text-green-500")),
        ("error", rx.icon("wheat", class_name="h-4 w-4 text-red-500")),
        rx.icon("file", class_name="h-4 w-4 text-gray-400"),
    )


def file_card(file: dict) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                file_status_icon(file["status"]),
                rx.el.div(
                    rx.el.span(
                        file["name"],
                        class_name="text-sm font-medium text-gray-700 dark:text-gray-200 truncate block max-w-[150px]",
                    ),
                    class_name="flex flex-col",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.button(
                rx.icon("x", class_name="h-4 w-4"),
                on_click=lambda: FileUploadState.remove_file(file["name"]),
                class_name="text-gray-400 hover:text-red-500 transition-colors",
            ),
            class_name="flex items-center justify-between",
        ),
        rx.cond(
            (file["status"] != "complete") & (file["status"] != "error"),
            rx.el.div(
                rx.el.div(
                    class_name="h-1 bg-indigo-600 rounded-full transition-all duration-300",
                    style={"width": f"{file['progress']}%"},
                ),
                class_name="w-full bg-gray-100 dark:bg-gray-700 h-1 rounded-full mt-3 overflow-hidden",
            ),
        ),
        class_name="p-3 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-xl shadow-sm hover:border-indigo-100 dark:hover:border-indigo-500 transition-all",
    )


def dropzone() -> rx.Component:
    return rx.upload.root(
        rx.el.div(
            rx.el.div(
                rx.icon(
                    "pen",
                    class_name=rx.cond(
                        FileUploadState.has_files,
                        "h-6 w-6 text-indigo-400 mb-2",
                        "h-10 w-10 text-indigo-400 mb-3",
                    ),
                ),
                rx.el.p(
                    "Click or drag to upload",
                    class_name=rx.cond(
                        FileUploadState.has_files,
                        "text-xs font-semibold text-gray-700 dark:text-gray-200",
                        "text-sm font-semibold text-gray-700 dark:text-gray-200",
                    ),
                ),
                rx.cond(
                    ~FileUploadState.has_files,
                    rx.el.p(
                        "PDF, TXT, DOCX up to 10MB",
                        class_name="text-xs text-gray-500 dark:text-gray-400 mt-1",
                    ),
                ),
                class_name=rx.cond(
                    FileUploadState.has_files,
                    "flex flex-col items-center justify-center p-4 text-center",
                    "flex flex-col items-center justify-center p-8 text-center",
                ),
            ),
            class_name="border-2 border-dashed border-gray-200 dark:border-gray-600 rounded-2xl hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50/30 dark:hover:bg-indigo-900/10 transition-all cursor-pointer group",
        ),
        id="file_upload",
        multiple=True,
        accept={
            "application/pdf": [".pdf"],
            "text/plain": [".txt"],
            "text/markdown": [".md"],
        },
        max_files=5,
        on_drop=FileUploadState.handle_upload(rx.upload_files(upload_id="file_upload")),
    )


def stats_bar() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                FileUploadState.total_docs_ready,
                class_name="text-sm font-bold text-indigo-600 dark:text-indigo-400",
            ),
            rx.el.span(
                " Docs",
                class_name="text-[10px] text-gray-400 dark:text-gray-500 font-medium",
            ),
            class_name="flex flex-col items-center bg-gray-50 dark:bg-gray-800/50 px-3 py-2 rounded-lg border border-gray-100 dark:border-gray-700 flex-1",
        ),
        rx.el.div(
            rx.el.span(
                FileUploadState.total_chunks,
                class_name="text-sm font-bold text-indigo-600 dark:text-indigo-400",
            ),
            rx.el.span(
                " Chunks",
                class_name="text-[10px] text-gray-400 dark:text-gray-500 font-medium",
            ),
            class_name="flex flex-col items-center bg-gray-50 dark:bg-gray-800/50 px-3 py-2 rounded-lg border border-gray-100 dark:border-gray-700 flex-1",
        ),
        class_name="flex gap-2 mb-6",
    )


def log_tearsheet() -> rx.Component:
    """
    Full-height tearsheet from the right showing pipeline logs.
    Visibility controlled via inline style display:none/block so Reflex
    state diffs always reach the mounted component.
    """
    return rx.el.div(
        # Backdrop
        rx.el.div(
            on_click=LogPollerState.close_logs,
            style=rx.cond(
                LogPollerState.show_logs,
                {
                    "position": "absolute",
                    "inset": "0",
                    "background": "rgba(0,0,0,0.5)",
                    "cursor": "pointer",
                },
                {"display": "none"},
            ),
        ),
        # Panel
        rx.el.div(
            # Header
            rx.el.div(
                rx.el.div(
                    rx.icon("terminal", class_name="h-4 w-4 text-green-400 mr-2"),
                    rx.el.span(
                        "Pipeline Logs",
                        class_name="text-sm font-semibold text-white",
                    ),
                    class_name="flex items-center",
                ),
                rx.el.button(
                    rx.icon("x", class_name="h-4 w-4 text-gray-400 hover:text-white"),
                    on_click=LogPollerState.close_logs,
                    class_name="p-1 rounded hover:bg-gray-700 transition-colors",
                ),
                class_name="flex items-center justify-between px-4 py-3 border-b border-gray-700 flex-shrink-0",
            ),
            # Status badge — color-coded: amber=running, green=success, red=error
            _status_badge(),
            # Log lines — reads from LogPollerState (background poller, separate lock)
            rx.el.div(
                rx.cond(
                    LogPollerState.log_lines.length() > 0,
                    rx.foreach(
                        LogPollerState.log_lines,
                        _log_line,
                    ),
                    rx.el.p(
                        rx.cond(
                            FileUploadState.is_processing,
                            "Starting pipeline — logs will appear here...",
                            "No logs available. Process documents to see pipeline output.",
                        ),
                        class_name="text-xs text-gray-500 italic mt-4 text-center",
                    ),
                ),
                id="pipeline-log-box",
                class_name="flex-1 overflow-y-auto p-4 flex flex-col gap-0",
            ),
            style={
                "position": "absolute",
                "right": "0",
                "top": "0",
                "height": "100%",
                "width": "480px",
                "maxWidth": "100%",
                "background": "#030712",
                "borderLeft": "1px solid #374151",
                "display": "flex",
                "flexDirection": "column",
                "boxShadow": "0 25px 50px -12px rgba(0,0,0,0.25)",
            },
        ),
        # Outer wrapper: always in DOM, hidden via display:none when closed
        style=rx.cond(
            LogPollerState.show_logs,
            {"position": "fixed", "inset": "0", "zIndex": "50"},
            {"display": "none"},
        ),
    )


def document_sidebar() -> rx.Component:
    return rx.el.aside(
        rx.el.div(
            rx.el.div(
                rx.el.h3(
                    "Documents",
                    class_name="text-base font-bold text-gray-800 dark:text-gray-100 mb-1",
                ),
                rx.el.p(
                    "Context for your AI Assistant",
                    class_name="text-xs text-gray-500 dark:text-gray-400 mb-6",
                ),
                class_name="flex-shrink-0",
            ),
            rx.cond(
                FileUploadState.has_files,
                rx.el.div(
                    # stats_bar(),
                    rx.el.div(
                        rx.foreach(FileUploadState.files, file_card),
                        class_name="flex flex-col gap-3 flex-1 overflow-y-auto min-h-0 pr-1 mb-4",
                    ),
                    rx.el.div(dropzone(), class_name="flex-shrink-0 mb-4"),
                    class_name="flex flex-col flex-1 min-h-0",
                ),
                rx.el.div(
                    dropzone(),
                    rx.el.div(
                        rx.icon("info", class_name="h-4 w-4 text-indigo-400"),
                        rx.el.p(
                            "Uploaded documents are used to ground AI responses.",
                            class_name="text-[11px] text-gray-500 dark:text-gray-400 leading-tight",
                        ),
                        class_name="flex items-start gap-2 mt-6 p-3 bg-indigo-50 dark:bg-indigo-900/20 rounded-xl",
                    ),
                    class_name="flex flex-col flex-1",
                ),
            ),
            # Process Documents button + View Logs button row
            rx.el.div(
                rx.el.button(
                    rx.cond(
                        FileUploadState.is_processing,
                        rx.el.div(
                            rx.icon(
                                "refresh-cw", class_name="h-4 w-4 animate-spin mr-2"
                            ),
                            "Processing...",
                            class_name="flex items-center justify-center",
                        ),
                        rx.el.div(
                            rx.icon("play", class_name="h-4 w-4 mr-2"),
                            "Process Documents",
                            class_name="flex items-center justify-center",
                        ),
                    ),
                    on_click=[
                        LogPollerState.start_polling,
                        FileUploadState.process_documents,
                    ],
                    disabled=FileUploadState.is_processing | ~FileUploadState.has_files,
                    class_name="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all shadow-sm hover:shadow-md",
                ),
                # View Logs button — shown while processing or when logs exist
                # Color: red=failed, amber=running, default gray otherwise
                rx.cond(
                    FileUploadState.is_processing
                    | (LogPollerState.log_lines.length() > 0),
                    rx.el.button(
                        rx.cond(
                            FileUploadState.processing_failed,
                            rx.icon("scroll-text", class_name="h-4 w-4 text-red-400"),
                            rx.cond(
                                FileUploadState.is_processing,
                                rx.icon(
                                    "scroll-text",
                                    class_name="h-4 w-4 animate-pulse text-amber-500",
                                ),
                                rx.icon(
                                    "scroll-text",
                                    class_name="h-4 w-4 text-gray-600 dark:text-gray-300",
                                ),
                            ),
                        ),
                        on_click=LogPollerState.open_logs,
                        title="View pipeline logs",
                        class_name=rx.cond(
                            FileUploadState.processing_failed,
                            "py-3 px-3 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 rounded-xl transition-all border border-red-200 dark:border-red-700",
                            rx.cond(
                                FileUploadState.is_processing,
                                "py-3 px-3 bg-amber-50 dark:bg-amber-900/20 hover:bg-amber-100 dark:hover:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded-xl transition-all border border-amber-200 dark:border-amber-700",
                                "py-3 px-3 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-xl transition-all border border-gray-200 dark:border-gray-600",
                            ),
                        ),
                    ),
                ),
                class_name="flex gap-2 flex-shrink-0 mt-4",
            ),
            class_name="flex flex-col h-full",
        ),
        class_name="bg-white dark:bg-gray-900 p-6 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 h-full overflow-hidden",
    )
