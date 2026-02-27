import reflex as rx
from chat_with_file_ingestion.states.file_state import FileUploadState


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
                    rx.el.span(
                        rx.match(
                            file["status"],
                            ("uploading", "Uploading..."),
                            ("processing", "Analyzing contents..."),
                            ("complete", "Ready for Q&A"),
                            ("error", file["error"]),
                            "Pending",
                        ),
                        class_name=rx.cond(
                            file["status"] == "error",
                            "text-[10px] text-red-500 uppercase tracking-wider",
                            "text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider",
                        ),
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
                    stats_bar(),
                    rx.el.div(
                        rx.foreach(FileUploadState.files, file_card),
                        class_name="flex flex-col gap-3 flex-1 overflow-y-auto min-h-0 pr-1 mb-4",
                    ),
                    rx.el.div(dropzone(), class_name="flex-shrink-0"),
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
            class_name="flex flex-col h-full",
        ),
        class_name="bg-white dark:bg-gray-900 p-6 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 h-full overflow-hidden",
    )