const uploadForm =
    document.getElementById(
        "uploadForm"
    );

const documentType =
    document.getElementById(
        "documentType"
    );

const documentFile =
    document.getElementById(
        "documentFile"
    );

const processButton =
    document.getElementById(
        "processButton"
    );

const messageBox =
    document.getElementById(
        "message"
    );

const documentsTable =
    document.getElementById(
        "documentsTable"
    );

const refreshButton =
    document.getElementById(
        "refreshButton"
    );

const apiStatus =
    document.getElementById(
        "apiStatus"
    );

const resultSection =
    document.getElementById(
        "resultSection"
    );

const resultTitle =
    document.getElementById(
        "resultTitle"
    );

const resultStatus =
    document.getElementById(
        "resultStatus"
    );

const fileValidation =
    document.getElementById(
        "fileValidation"
    );

const extractedFields =
    document.getElementById(
        "extractedFields"
    );

const lineItemsSection =
    document.getElementById(
        "lineItemsSection"
    );

const lineItems =
    document.getElementById(
        "lineItems"
    );

const additionalFieldsSection =
    document.getElementById(
        "additionalFieldsSection"
    );

const additionalFields =
    document.getElementById(
        "additionalFields"
    );

const validationSummary =
    document.getElementById(
        "validationSummary"
    );

const validationChecks =
    document.getElementById(
        "validationChecks"
    );

const rawJson =
    document.getElementById(
        "rawJson"
    );


function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


function prettyName(value) {

    return String(value)
        .replaceAll(
            "_",
            " "
        )
        .replace(
            /\b\w/g,
            char =>
                char.toUpperCase()
        );
}


function showMessage(
    text,
    type = "success"
) {

    messageBox.textContent =
        text;

    messageBox.className =
        "message";

    if (
        type === "error"
    ) {
        messageBox.classList.add(
            "message-error"
        );
    } else {
        messageBox.classList.add(
            "message-success"
        );
    }
}


function hideMessage() {

    messageBox.classList.add(
        "hidden"
    );
}


function statusClass(
    status
) {

    const normalized =
        String(
            status || ""
        ).toUpperCase();

    if (
        normalized === "PASS"
    ) {
        return "status-pass";
    }

    if (
        normalized === "FAILED" ||
        normalized === "FAIL"
    ) {
        return "status-failed";
    }

    return "status-na";
}


async function checkHealth() {

    try {

        const response =
            await fetch(
                "/api/v1/health"
            );

        if (
            !response.ok
        ) {
            throw new Error(
                "Health API failed"
            );
        }

        const data =
            await response.json();

        apiStatus.textContent =
            data.status === "healthy"
                ? "API Healthy"
                : "API Available";

        apiStatus.className =
            "health-badge status-pass";

    } catch (error) {

        apiStatus.textContent =
            "API Unavailable";

        apiStatus.className =
            "health-badge status-failed";
    }
}


function normalizeDocuments(
    data
) {

    if (
        Array.isArray(
            data
        )
    ) {
        return data;
    }

    if (
        Array.isArray(
            data.documents
        )
    ) {
        return data.documents;
    }

    if (
        Array.isArray(
            data.items
        )
    ) {
        return data.items;
    }

    if (
        Array.isArray(
            data.results
        )
    ) {
        return data.results;
    }

    if (
        Array.isArray(
            data.records
        )
    ) {
        return data.records;
    }

    return [];
}


function getDocumentName(
    record
) {

    return (
        record.document_name ||
        record.file_name ||
        record.filename ||
        record.name ||
        "-"
    );
}


function getDocumentType(
    record
) {

    return (
        record.document_type ||
        record.type ||
        "-"
    );
}


function getDocumentStatus(
    record
) {

    return (
        record.processing_status ||
        record.status ||
        record.financial_validation
            ?.overall_status ||
        "-"
    );
}


function getProcessedTime(
    record
) {

    const value =
        record.processed_at ||
        record.created_at ||
        record.updated_at ||
        record.timestamp ||
        "-";

    if (
        value === "-"
    ) {
        return value;
    }

    try {

        return new Date(
            value
        ).toLocaleString();

    } catch {

        return value;
    }
}


async function loadDocuments() {

    documentsTable.innerHTML = `
        <tr>
            <td colspan="5">
                Loading...
            </td>
        </tr>
    `;

    try {

        const response =
            await fetch(
                "/api/v1/documents"
            );

        if (
            !response.ok
        ) {
            throw new Error(
                "Unable to load documents"
            );
        }

        const data =
            await response.json();

        const documents =
            normalizeDocuments(
                data
            );

        if (
            documents.length === 0
        ) {

            documentsTable.innerHTML = `
                <tr>
                    <td colspan="5">
                        No processed documents yet.
                    </td>
                </tr>
            `;

            return;
        }

        documentsTable.innerHTML =
            "";

        for (
            const record
            of documents
        ) {

            const name =
                getDocumentName(
                    record
                );

            const type =
                getDocumentType(
                    record
                );

            const status =
                getDocumentStatus(
                    record
                );

            const processed =
                getProcessedTime(
                    record
                );

            const row =
                document.createElement(
                    "tr"
                );

            row.innerHTML = `
                <td>
                    ${escapeHtml(name)}
                </td>

                <td>
                    ${escapeHtml(
                        prettyName(type)
                    )}
                </td>

                <td>
                    <span
                        class="
                            status-badge
                            ${statusClass(status)}
                        "
                    >
                        ${escapeHtml(status)}
                    </span>
                </td>

                <td>
                    ${escapeHtml(processed)}
                </td>

                <td>
                    <button
                        class="view-button"
                        type="button"
                    >
                        View
                    </button>
                </td>
            `;

            const button =
                row.querySelector(
                    ".view-button"
                );

            button.addEventListener(
                "click",
                () =>
                    loadDocumentResult(
                        name
                    )
            );

            documentsTable.appendChild(
                row
            );
        }

    } catch (error) {

        documentsTable.innerHTML = `
            <tr>
                <td colspan="5">
                    Failed to load processed documents.
                </td>
            </tr>
        `;
    }
}


function renderKeyValueGrid(
    container,
    data
) {

    container.innerHTML =
        "";

    for (
        const [
            key,
            value
        ]
        of Object.entries(
            data || {}
        )
    ) {

        let displayValue =
            value;

        if (
            value &&
            typeof value === "object" &&
            !Array.isArray(value) &&
            Object.prototype.hasOwnProperty.call(
                value,
                "value"
            )
        ) {

            displayValue =
                value.value;
        }

        if (
            Array.isArray(
                displayValue
            )
        ) {

            if (
                displayValue.length === 0
            ) {
                displayValue =
                    null;
            } else {

                displayValue =
                    displayValue
                        .map(
                            item => {

                                if (
                                    item &&
                                    typeof item
                                    === "object" &&
                                    Object.prototype
                                        .hasOwnProperty
                                        .call(
                                            item,
                                            "period"
                                        )
                                ) {

                                    return (
                                        `${item.period}: ` +
                                        `${item.value}`
                                    );
                                }

                                return JSON.stringify(
                                    item
                                );
                            }
                        )
                        .join(
                            " | "
                        );
            }
        }

        if (
            displayValue &&
            typeof displayValue
            === "object"
        ) {

            displayValue =
                JSON.stringify(
                    displayValue
                );
        }

        const card =
            document.createElement(
                "div"
            );

        card.className =
            "kv-item";

        card.innerHTML = `
            <div class="kv-key">
                ${escapeHtml(
                    prettyName(key)
                )}
            </div>

            <div class="kv-value">
                ${
                    displayValue === null ||
                    displayValue === undefined ||
                    displayValue === ""
                        ? "NULL"
                        : escapeHtml(
                            displayValue
                        )
                }
            </div>
        `;

        container.appendChild(
            card
        );
    }
}


function renderGenericTable(
    container,
    rows
) {

    if (
        !rows ||
        rows.length === 0
    ) {

        container.innerHTML =
            "";

        return;
    }

    const keys =
        new Set();

    rows.forEach(
        row => {

            Object.keys(
                row || {}
            ).forEach(
                key => {

                    if (
                        key !== "evidence"
                    ) {
                        keys.add(
                            key
                        );
                    }
                }
            );
        }
    );

    const columns =
        Array.from(
            keys
        );

    let html = `
        <table>

            <thead>

                <tr>
    `;

    for (
        const column
        of columns
    ) {

        html += `
            <th>
                ${escapeHtml(
                    prettyName(column)
                )}
            </th>
        `;
    }

    html += `
                </tr>

            </thead>

            <tbody>
    `;

    for (
        const row
        of rows
    ) {

        html += `
            <tr>
        `;

        for (
            const column
            of columns
        ) {

            let value =
                row[
                    column
                ];

            if (
                Array.isArray(
                    value
                )
            ) {

                value =
                    value
                        .map(
                            item => {

                                if (
                                    item &&
                                    typeof item
                                    === "object"
                                ) {

                                    if (
                                        "period"
                                        in item
                                    ) {

                                        return (
                                            `${item.period}: ` +
                                            `${item.value}`
                                        );
                                    }

                                    return JSON.stringify(
                                        item
                                    );
                                }

                                return item;
                            }
                        )
                        .join(
                            " | "
                        );
            }

            if (
                value &&
                typeof value
                === "object"
            ) {

                value =
                    JSON.stringify(
                        value
                    );
            }

            html += `
                <td>
                    ${
                        value === null ||
                        value === undefined
                            ? "NULL"
                            : escapeHtml(
                                value
                            )
                    }
                </td>
            `;
        }

        html += `
            </tr>
        `;
    }

    html += `
            </tbody>

        </table>
    `;

    container.innerHTML =
        html;
}


function renderValidation(
    validation
) {

    const summary =
        validation?.summary || {};

    validationSummary.innerHTML = `
        <div class="summary-box">
            Total:
            <strong>
                ${summary.total_checks ?? 0}
            </strong>
        </div>

        <div class="summary-box">
            Passed:
            <strong>
                ${summary.passed ?? 0}
            </strong>
        </div>

        <div class="summary-box">
            Failed:
            <strong>
                ${summary.failed ?? 0}
            </strong>
        </div>

        <div class="summary-box">
            N/A:
            <strong>
                ${summary.not_applicable ?? 0}
            </strong>
        </div>
    `;

    const checks =
        validation?.checks || [];

    if (
        checks.length === 0
    ) {

        validationChecks.innerHTML =
            "<p>No validation checks available.</p>";

        return;
    }

    let html = `
        <table>

            <thead>

                <tr>
                    <th>
                        Check
                    </th>

                    <th>
                        Formula
                    </th>

                    <th>
                        Calculated
                    </th>

                    <th>
                        Reported
                    </th>

                    <th>
                        Variance
                    </th>

                    <th>
                        Status
                    </th>
                </tr>

            </thead>

            <tbody>
    `;

    for (
        const check
        of checks
    ) {

        const status =
            check.status ||
            "NOT_APPLICABLE";

        html += `
            <tr>

                <td>
                    ${escapeHtml(
                        check.check_name ||
                        check.name ||
                        check.check_id ||
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        check.formula ||
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        check.calculated_value ??
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        check.reported_value ??
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        check.variance ??
                        "-"
                    )}
                </td>

                <td>
                    <span
                        class="
                            status-badge
                            ${statusClass(status)}
                        "
                    >
                        ${escapeHtml(status)}
                    </span>
                </td>

            </tr>
        `;
    }

    html += `
            </tbody>

        </table>
    `;

    validationChecks.innerHTML =
        html;
}


function renderResult(
    data
) {

    resultSection.classList.remove(
        "hidden"
    );

    resultTitle.textContent =
        `${data.document_name || "-"} • ` +
        `${prettyName(
            data.document_type || "-"
        )}`;

    const status =
        data.processing_status ||
        data.financial_validation
            ?.overall_status ||
        data.status ||
        "UNKNOWN";

    resultStatus.textContent =
        status;

    resultStatus.className =
        `status-badge ${statusClass(status)}`;


    renderKeyValueGrid(
        fileValidation,
        data.file_validation || {}
    );


    const extracted =
        data.extracted_data || {};

    const mainFields = {};

    for (
        const [
            key,
            value
        ]
        of Object.entries(
            extracted
        )
    ) {

        if (
            key === "line_items" ||
            key === "additional_fields" ||
            key === "cash_balance_adjustments"
        ) {
            continue;
        }

        mainFields[
            key
        ] = value;
    }

    renderKeyValueGrid(
        extractedFields,
        mainFields
    );


    const extractedRows =
        extracted.line_items || [];

    if (
        extractedRows.length > 0
    ) {

        lineItemsSection
            .classList
            .remove(
                "hidden"
            );

        renderGenericTable(
            lineItems,
            extractedRows
        );

    } else {

        lineItemsSection
            .classList
            .add(
                "hidden"
            );
    }


    const extraRows =
        extracted.additional_fields || [];

    if (
        extraRows.length > 0
    ) {

        additionalFieldsSection
            .classList
            .remove(
                "hidden"
            );

        renderGenericTable(
            additionalFields,
            extraRows
        );

    } else {

        additionalFieldsSection
            .classList
            .add(
                "hidden"
            );
    }


    renderValidation(
        data.financial_validation || {}
    );


    rawJson.textContent =
        JSON.stringify(
            data,
            null,
            2
        );


    resultSection.scrollIntoView(
        {
            behavior:
                "smooth"
        }
    );
}


async function loadDocumentResult(
    documentName
) {

    try {

        const response =
            await fetch(
                "/api/v1/documents/"
                + encodeURIComponent(
                    documentName
                )
            );

        const data =
            await response.json();

        if (
            !response.ok
        ) {

            throw new Error(
                data?.error?.message ||
                data?.detail ||
                "Unable to load document."
            );
        }

        renderResult(
            data
        );

    } catch (error) {

        showMessage(
            error.message,
            "error"
        );
    }
}


uploadForm.addEventListener(
    "submit",
    async event => {

        event.preventDefault();

        hideMessage();


        if (
            !documentType.value
        ) {

            showMessage(
                "Please select a document type.",
                "error"
            );

            return;
        }


        if (
            !documentFile.files.length
        ) {

            showMessage(
                "Please choose a document.",
                "error"
            );

            return;
        }


        const formData =
            new FormData();

        formData.append(
            "file",
            documentFile.files[0]
        );

        formData.append(
            "document_type",
            documentType.value
        );


        processButton.disabled =
            true;

        processButton.textContent =
            "Processing...";


        try {

            const response =
                await fetch(
                    "/api/v1/documents/process",
                    {
                        method:
                            "POST",

                        body:
                            formData,
                    }
                );

            const data =
                await response.json();

            if (
                !response.ok
            ) {

                throw new Error(
                    data?.error?.message ||
                    data?.detail ||
                    "Document processing failed."
                );
            }


            showMessage(
                "Document processed successfully."
            );


            renderResult(
                data
            );


            await loadDocuments();


        } catch (error) {

            showMessage(
                error.message,
                "error"
            );

        } finally {

            processButton.disabled =
                false;

            processButton.textContent =
                "Process Document";
        }
    }
);


refreshButton.addEventListener(
    "click",
    loadDocuments
);


checkHealth();

loadDocuments();