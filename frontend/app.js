// ==================================================
// VARIABLES
// ==================================================

let socket = null;

let audioContext = null;
let microphone = null;
let processor = null;
let audioStream = null;

let isRecording = false;
let isConnecting = false;
let reconnectTimer = null;
let sessionId = null;

let elevenLabsAudioChunks = [];
let elevenLabsAudio = null;
let currentAudioRequestId = null;

const RECONNECT_DELAY_MS = 3000;
const SESSION_STORAGE_KEY = "jarvis_session_id";


// ==================================================
// ELEMENTS
// ==================================================

const sendButton =
    document.getElementById("sendButton");

const messageInput =
    document.getElementById("messageInput");

const voiceButton =
    document.getElementById("voiceButton");

const micLabel =
    document.getElementById("micLabel");

const status =
    document.getElementById("status");

const systemStatus =
    document.getElementById("systemStatus");

const responseBox =
    document.getElementById("response");

const liveTranscript =
    document.getElementById("liveTranscript");

const toolName =
    document.getElementById("toolName");

const toolState =
    document.getElementById("toolState");

const toolStatus =
    document.getElementById("toolStatus");

const reminderFeed =
    document.getElementById("reminderFeed");

const voiceStatus =
    document.getElementById("voiceStatus");

const VOICE_STATUS_LABELS = {
    disconnected: "Offline",
    connecting: "Connecting",
    connected: "Ready",
    listening: "Listening",
    processing: "Thinking",
    speaking: "Speaking",
    error: "Error",
};


// ==================================================
// UI STATE
// ==================================================

function setBodyState(state) {

    document.body.className =
        "state-" + state;

    if (voiceStatus) {

        voiceStatus.textContent =
            VOICE_STATUS_LABELS[state]
            || state;

    }

}


function setConnectionStatus(label) {

    status.textContent = label;

}


function setSystemStatus(label) {

    systemStatus.textContent = label;

}


function updateTranscript(
    text,
    isFinal
) {

    liveTranscript.className =
        "transcript-content " +
        (isFinal ? "final" : "interim");

    liveTranscript.innerHTML =
        '<span class="transcript-prefix">🎤</span>' +
        '<span class="transcript-text">' +
        escapeHtml(text) +
        "</span>";

}


function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;

}


function setMicLabel(text) {

    micLabel.textContent = text;

}


function formatToolLabel(tool) {

    const labels = {
        weather: "WEATHER",
        create_reminder: "CREATE REMINDER",
        get_reminders: "LIST REMINDERS",
        cancel_reminder: "CANCEL REMINDER",
    };

    return labels[tool] || String(tool || "TOOL").toUpperCase();

}


function updateToolStatus(
    tool,
    status
) {

    toolName.textContent = formatToolLabel(tool);

    if (status === "started") {

        toolState.textContent = "EXECUTING...";
        toolStatus.className = "tool-status-content executing";

    }
    else if (
        status === "completed"
        || status === "saved"
    ) {

        toolState.textContent = status === "saved"
            ? "SAVED"
            : "COMPLETED";
        toolStatus.className = "tool-status-content completed";

    }
    else {

        toolState.textContent = String(status || "READY").toUpperCase();
        toolStatus.className = "tool-status-content";

    }

}


function showToolError(
    tool,
    text
) {

    toolName.textContent = formatToolLabel(tool);
    toolState.textContent = text || "ERROR";
    toolStatus.className = "tool-status-content error";

}


function showReminderInHud(text) {

    const item = document.createElement("div");

    item.className = "reminder-item";
    item.textContent = text;

    if (
        reminderFeed.textContent.includes(
            "No active reminders"
        )
    ) {

        reminderFeed.textContent = "";

    }

    reminderFeed.prepend(item);

}


function showBrowserNotification(text) {

    if (
        !("Notification" in window)
        || Notification.permission !== "granted"
    ) {

        return;

    }

    new Notification(
        "JARVIS",
        {
            body: text,
        }
    );

}


function requestNotificationPermission() {

    if (!("Notification" in window)) {
        return;
    }

    if (Notification.permission === "default") {

        Notification.requestPermission().catch(
            () => {}
        );

    }

}


function restoreSessionId() {

    try {

        return sessionStorage.getItem(
            SESSION_STORAGE_KEY
        );

    }
    catch (error) {

        return null;

    }

}


function storeSessionId(value) {

    try {

        sessionStorage.setItem(
            SESSION_STORAGE_KEY,
            value
        );

    }
    catch (error) {

        console.warn(
            "Could not store session id:",
            error
        );

    }

}


function sendSessionRestore() {

    const storedSessionId = restoreSessionId();

    if (
        !storedSessionId
        || !socket
        || socket.readyState !== WebSocket.OPEN
    ) {

        return;

    }

    socket.send(
        JSON.stringify({
            type: "session",
            session_id: storedSessionId,
        })
    );

}


function scheduleReconnect() {

    if (reconnectTimer) {
        return;
    }

    reconnectTimer = setTimeout(() => {

        reconnectTimer = null;

        if (
            !socket ||
            socket.readyState === WebSocket.CLOSED
        ) {

            connectToBackend();

        }

    }, RECONNECT_DELAY_MS);

}


// ==================================================
// WEBSOCKET CONNECT
// ==================================================

window.addEventListener(
    "load",
    () => {

        requestNotificationPermission();
        connectToBackend();

    }
);


function connectToBackend() {

    if (
        socket &&
        socket.readyState === WebSocket.OPEN
    ) {

        console.log(
            "Already connected."
        );

        setConnectionStatus("CONNECTED");
        setSystemStatus("● ONLINE");
        setBodyState("connected");

        return;
    }

    if (
        socket &&
        socket.readyState === WebSocket.CONNECTING
    ) {

        return;
    }

    if (isConnecting) {
        return;
    }

    isConnecting = true;

    console.log(
        "🔌 Connecting to backend..."
    );

    setConnectionStatus("CONNECTING");
    setSystemStatus("● CONNECTING");
    setBodyState("connecting");

    const protocol =
        window.location.protocol === "https:"
            ? "wss:"
            : "ws:";

    const wsUrl =
        protocol + "//" + window.location.host + "/ws";

    socket = new WebSocket(wsUrl);


    // ==================================================
    // SOCKET OPEN
    // ==================================================

    socket.onopen = () => {

        isConnecting = false;

        console.log(
            "🟢 Connected to backend"
        );

        setConnectionStatus("CONNECTED");
        setSystemStatus("● ONLINE");
        setBodyState("connected");

        sendSessionRestore();

    };


    // ==================================================
    // SOCKET MESSAGE
    // ==================================================

    socket.onmessage = (event) => {

        console.log(
            "📨 Backend:",
            event.data
        );


        let parsed;


        // ------------------------------------------
        // TRY JSON
        // ------------------------------------------

        try {

            parsed =
                JSON.parse(event.data);

        }
        catch (error) {

            console.log(
                "Plain text received:",
                event.data
            );

            showAssistantResponse(
                event.data
            );

            return;
        }


        // ==================================================
        // SESSION
        // ==================================================

        if (
            parsed.type ===
            "session"
        ) {

            sessionId = parsed.session_id || null;

            if (sessionId) {

                storeSessionId(sessionId);

                console.log(
                    "🔑 Session:",
                    sessionId
                );

            }

            return;
        }


        // ==================================================
        // TOOL STATUS
        // ==================================================

        if (
            parsed.type ===
            "tool"
        ) {

            updateToolStatus(
                parsed.tool,
                parsed.status
            );

            return;
        }


        if (
            parsed.type ===
            "tool_error"
        ) {

            showToolError(
                parsed.tool,
                parsed.text
            );

            return;
        }


        // ==================================================
        // REMINDER
        // ==================================================

        if (
            parsed.type ===
            "reminder"
        ) {

            const reminderText =
                parsed.text || "Reminder";

            console.log(
                "⏰ Reminder:",
                reminderText
            );

            showReminderInHud(reminderText);
            showBrowserNotification(reminderText);

            return;
        }


        // ==================================================
        // TRANSCRIPT
        // ==================================================

        if (
            parsed.type ===
            "transcript"
        ) {

            const transcript =
                parsed.text || "";


            if (!transcript) {
                return;
            }


            console.log(
                "🎤 Transcript:",
                transcript
            );


            // ------------------------------------------
            // LIVE TRANSCRIPT
            // ------------------------------------------

            updateTranscript(
                transcript,
                parsed.final
            );


            // ------------------------------------------
            // PUT TRANSCRIPT INTO TEXT BAR
            // ------------------------------------------

            messageInput.value =
                transcript;


            // ------------------------------------------
            // STATUS
            // ------------------------------------------

            if (parsed.final) {

                setConnectionStatus(
                    "FINAL: " + transcript
                );

                setSystemStatus(
                    "● PROCESSING"
                );

                setBodyState("processing");

            }
            else {

                setConnectionStatus(
                    transcript
                );

                setSystemStatus(
                    "● LISTENING"
                );

                setBodyState("listening");

            }


            return;
        }


        // ==================================================
        // ELEVENLABS AUDIO (streaming)
        // ==================================================

        if (parsed.type === "audio_start") {

            elevenLabsAudioChunks = [];
            currentAudioRequestId =
                parsed.request_id || null;

            if (elevenLabsAudio) {

                elevenLabsAudio.pause();
                elevenLabsAudio = null;

            }

            window.speechSynthesis.cancel();

            return;
        }


        if (parsed.type === "audio_chunk") {

            if (parsed.data) {

                const binary = atob(parsed.data);
                const bytes = new Uint8Array(binary.length);

                for (let i = 0; i < binary.length; i++) {

                    bytes[i] = binary.charCodeAt(i);

                }

                elevenLabsAudioChunks.push(bytes);

            }

            return;
        }


        if (parsed.type === "audio_end") {

            if (elevenLabsAudioChunks.length > 0) {

                playElevenLabsAudio(
                    elevenLabsAudioChunks,
                    currentAudioRequestId
                );

            }

            elevenLabsAudioChunks = [];

            return;
        }


        if (parsed.type === "audio") {

            if (parsed.data) {

                const binary = atob(parsed.data);
                const bytes = new Uint8Array(binary.length);

                for (let i = 0; i < binary.length; i++) {

                    bytes[i] = binary.charCodeAt(i);

                }

                playElevenLabsAudio(
                    [bytes],
                    parsed.request_id || null
                );

            }

            return;
        }


        // ==================================================
        // ASSISTANT RESPONSE
        // ==================================================

        if (
            parsed.type ===
            "assistant"
            ||
            parsed.type ===
            "response"
        ) {

            const answer =
                parsed.text ||
                parsed.response ||
                "";


            if (answer) {

                showAssistantResponse(
                    answer,
                    { speak: false }
                );

            }


            return;
        }


        // ==================================================
        // ERROR
        // ==================================================

        if (
            parsed.type ===
            "error"
        ) {

            console.error(
                "❌ Backend error:",
                parsed.text
            );


            setConnectionStatus(
                "ERROR"
            );

            setSystemStatus(
                "● ERROR"
            );

            setBodyState("error");


            return;
        }


        // ==================================================
        // OTHER JSON MESSAGE
        // ==================================================

        const genericText =
            parsed.text ||
            parsed.response ||
            "";


        if (genericText) {

            showAssistantResponse(
                genericText
            );

        }

    };


    // ==================================================
    // SOCKET CLOSE
    // ==================================================

    socket.onclose = () => {

        isConnecting = false;

        console.log(
            "🔴 Backend disconnected"
        );

        setConnectionStatus("DISCONNECTED");
        setSystemStatus("● OFFLINE");
        setBodyState("disconnected");

        socket = null;

        scheduleReconnect();

    };


    // ==================================================
    // SOCKET ERROR
    // ==================================================

    socket.onerror = (error) => {

        isConnecting = false;

        console.error(
            "❌ WebSocket error:",
            error
        );

        setConnectionStatus("ERROR");
        setSystemStatus("● ERROR");
        setBodyState("error");

    };

}


// ==================================================
// ASSISTANT RESPONSE
// ==================================================

function showAssistantResponse(text, options = {}) {

    responseBox.textContent = text;

    setConnectionStatus("RESPONDING");
    setSystemStatus("● SPEAKING");
    setBodyState("speaking");


    if (options.speak !== false) {

        speakResponse(text);

    }

}


function sendPlaybackStartLatency(requestId) {

    if (
        !requestId ||
        !socket ||
        socket.readyState !== WebSocket.OPEN
    ) {

        return;

    }

    socket.send(
        JSON.stringify({
            type: "latency",
            event: "playback_start",
            request_id: requestId,
        })
    );

}


async function playElevenLabsAudio(
    chunks,
    requestId
) {

    if (elevenLabsAudio) {

        elevenLabsAudio.pause();
        elevenLabsAudio = null;

    }

    window.speechSynthesis.cancel();


    const blob = new Blob(
        chunks,
        { type: "audio/mpeg" }
    );

    const url = URL.createObjectURL(blob);

    elevenLabsAudio = new Audio(url);


    elevenLabsAudio.onplay = () => {

        setBodyState("speaking");
        setSystemStatus("● SPEAKING");

        sendPlaybackStartLatency(requestId);

        currentAudioRequestId = null;

    };


    elevenLabsAudio.onended = () => {

        URL.revokeObjectURL(url);
        elevenLabsAudio = null;


        if (
            socket &&
            socket.readyState === WebSocket.OPEN
        ) {

            setBodyState("connected");
            setSystemStatus("● ONLINE");
            setConnectionStatus("CONNECTED");

        }

    };


    elevenLabsAudio.onerror = () => {

        URL.revokeObjectURL(url);
        elevenLabsAudio = null;

        const fallbackText =
            responseBox.textContent;

        if (fallbackText) {

            speakResponse(fallbackText);

        }

    };


    try {

        await elevenLabsAudio.play();

    }
    catch (error) {

        console.error(
            "ElevenLabs playback failed:",
            error
        );

        const fallbackText =
            responseBox.textContent;

        if (fallbackText) {

            speakResponse(fallbackText);

        }

    }

}


// ==================================================
// TEXT SEND
// ==================================================

sendButton.addEventListener(
    "click",
    sendTextMessage
);


function sendTextMessage() {

    if (
        !socket ||
        socket.readyState !==
        WebSocket.OPEN
    ) {

        setConnectionStatus("DISCONNECTED");
        setSystemStatus("● OFFLINE");

        return;
    }


    const message =
        messageInput.value.trim();


    if (!message) {
        return;
    }


    console.log(
        "📤 Sending text:",
        message
    );


    setSystemStatus("● PROCESSING");
    setBodyState("processing");


    socket.send(
        message
    );


    messageInput.value = "";

}


// ==================================================
// ENTER KEY
// ==================================================

messageInput.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key ===
            "Enter"
        ) {

            sendTextMessage();

        }

    }
);


// ==================================================
// START / STOP RECORDING
// ==================================================

voiceButton.addEventListener(
    "click",
    async () => {

        if (isRecording) {

            stopRecording();

        }
        else {

            await startRecording();

        }

    }
);


// ==================================================
// START RECORDING
// ==================================================

async function startRecording() {

    // ----------------------------------------------
    // CHECK SOCKET
    // ----------------------------------------------

    if (
        !socket ||
        socket.readyState !==
        WebSocket.OPEN
    ) {

        setConnectionStatus("DISCONNECTED");
        setSystemStatus("● OFFLINE");

        return;
    }


    try {

        // ------------------------------------------
        // MICROPHONE
        // ------------------------------------------

        audioStream =
            await navigator
                .mediaDevices
                .getUserMedia({
                    audio: true
                });


        console.log(
            "🎤 Microphone permission granted"
        );


        // ------------------------------------------
        // AUDIO CONTEXT
        // ------------------------------------------

        audioContext =
            new AudioContext();


        console.log(
            "🎧 Browser sample rate:",
            audioContext.sampleRate
        );


        // ------------------------------------------
        // RESUME AUDIO CONTEXT
        // ------------------------------------------

        if (
            audioContext.state ===
            "suspended"
        ) {

            await audioContext.resume();

        }


        // ------------------------------------------
        // MICROPHONE SOURCE
        // ------------------------------------------

        microphone =
            audioContext
                .createMediaStreamSource(
                    audioStream
                );


        // ------------------------------------------
        // SCRIPT PROCESSOR
        // ------------------------------------------

        processor =
            audioContext.createScriptProcessor(
                4096,
                1,
                1
            );


        // ------------------------------------------
        // AUDIO PROCESSING
        // ------------------------------------------

        processor.onaudioprocess =
            (event) => {

                if (!isRecording) {
                    return;
                }


                if (
                    !socket ||
                    socket.readyState !==
                    WebSocket.OPEN
                ) {

                    console.warn(
                        "⚠️ WebSocket not open"
                    );

                    return;
                }


                // Get microphone samples
                const input =
                    event
                        .inputBuffer
                        .getChannelData(0);


                // ----------------------------------
                // DOWNSAMPLE TO 16 KHZ
                // ----------------------------------

                const downsampled =
                    downsampleTo16k(
                        input,
                        audioContext.sampleRate
                    );


                // ----------------------------------
                // FLOAT32 → INT16
                // ----------------------------------

                const pcm =
                    floatTo16BitPCM(
                        downsampled
                    );


                if (
                    pcm.byteLength === 0
                ) {

                    return;

                }


                // ----------------------------------
                // SEND PCM TO BACKEND
                // ----------------------------------

                try {

                    socket.send(
                        pcm
                    );


                    console.log(
                        "🎤 Sending 16k PCM:",
                        pcm.byteLength,
                        "bytes"
                    );

                }
                catch (error) {

                    console.error(
                        "❌ PCM send error:",
                        error
                    );

                }

            };


        // ------------------------------------------
        // CONNECT AUDIO NODES
        // ------------------------------------------

        microphone.connect(
            processor
        );


        processor.connect(
            audioContext.destination
        );


        // ------------------------------------------
        // START
        // ------------------------------------------

        isRecording = true;

        voiceButton.classList.add("recording");

        setMicLabel("STOP LISTENING");

        setConnectionStatus("LISTENING");
        setSystemStatus("● LISTENING");
        setBodyState("listening");

        updateTranscript(
            "Listening...",
            false
        );


        console.log(
            "🎤 Recording started"
        );

    }
    catch (error) {

        console.error(
            "❌ Microphone error:",
            error
        );

        setConnectionStatus("ERROR");
        setSystemStatus("● ERROR");
        setBodyState("error");

    }

}


// ==================================================
// STOP RECORDING
// ==================================================

function stopRecording() {

    console.log(
        "🛑 Stopping recording..."
    );


    // ----------------------------------------------
    // STOP SENDING NEW AUDIO
    // ----------------------------------------------

    isRecording = false;

    voiceButton.classList.remove("recording");

    setMicLabel("START LISTENING");

    setConnectionStatus("FINALIZING");
    setSystemStatus("● PROCESSING");
    setBodyState("processing");


    // ----------------------------------------------
    // DISCONNECT PROCESSOR
    // ----------------------------------------------

    if (processor) {

        processor.disconnect();

        processor.onaudioprocess =
            null;

        processor = null;

    }


    // ----------------------------------------------
    // DISCONNECT MICROPHONE
    // ----------------------------------------------

    if (microphone) {

        microphone.disconnect();

        microphone = null;

    }


    // ----------------------------------------------
    // STOP MICROPHONE
    // ----------------------------------------------

    if (audioStream) {

        audioStream
            .getTracks()
            .forEach(
                track =>
                    track.stop()
            );

        audioStream = null;

    }


    // ----------------------------------------------
    // CLOSE AUDIO CONTEXT
    // ----------------------------------------------

    if (audioContext) {

        audioContext
            .close()
            .catch(
                () => {}
            );

        audioContext = null;

    }


    // ==================================================
    // IMPORTANT:
    // TELL BACKEND TO FINALIZE DEEPGRAM
    // ==================================================

    if (
        socket &&
        socket.readyState ===
        WebSocket.OPEN
    ) {

        try {

            socket.send(
                JSON.stringify({
                    type: "finalize"
                })
            );


            console.log(
                "🏁 Sent finalize to backend"
            );

        }
        catch (error) {

            console.error(
                "❌ Finalize send error:",
                error
            );

        }

    }
    else {

        console.warn(
            "⚠️ Cannot send finalize - socket is not open"
        );

    }


    console.log(
        "🎤 Recording stopped"
    );

}


// ==================================================
// DOWNSAMPLE TO 16 KHZ
// ==================================================

function downsampleTo16k(
    inputData,
    inputSampleRate
) {

    const outputSampleRate =
        16000;


    // Already 16 kHz
    if (
        inputSampleRate ===
        outputSampleRate
    ) {

        return inputData;

    }


    const ratio =
        inputSampleRate /
        outputSampleRate;


    const newLength =
        Math.round(
            inputData.length /
            ratio
        );


    const result =
        new Float32Array(
            newLength
        );


    let offsetResult = 0;
    let offsetBuffer = 0;


    while (
        offsetResult <
        result.length
    ) {

        const nextOffsetBuffer =
            Math.round(
                (
                    offsetResult +
                    1
                ) *
                ratio
            );


        let accumulator = 0;
        let count = 0;


        for (
            let i = offsetBuffer;
            i < nextOffsetBuffer &&
            i < inputData.length;
            i++
        ) {

            accumulator +=
                inputData[i];

            count++;

        }


        result[offsetResult] =
            count > 0
                ? accumulator / count
                : 0;


        offsetResult++;


        offsetBuffer =
            nextOffsetBuffer;

    }


    return result;

}


// ==================================================
// FLOAT32 → INT16 PCM
// ==================================================

function floatTo16BitPCM(
    float32Array
) {

    const buffer =
        new ArrayBuffer(
            float32Array.length * 2
        );


    const view =
        new DataView(
            buffer
        );


    let offset = 0;


    for (
        let i = 0;
        i < float32Array.length;
        i++
    ) {

        let sample =
            Math.max(
                -1,
                Math.min(
                    1,
                    float32Array[i]
                )
            );


        const value =
            sample < 0
                ? sample * 0x8000
                : sample * 0x7FFF;


        view.setInt16(
            offset,
            value,
            true
        );


        offset += 2;

    }


    return buffer;

}


// ==================================================
// TEXT TO SPEECH
// ==================================================

function speakResponse(text) {

    if (
        !window.speechSynthesis
    ) {

        console.log(
            "Browser speech synthesis unavailable"
        );

        setBodyState("connected");
        setSystemStatus("● ONLINE");
        setConnectionStatus("CONNECTED");

        return;

    }


    window.speechSynthesis.cancel();


    const speech =
        new SpeechSynthesisUtterance(
            text
        );


    speech.lang =
        "en-US";


    speech.rate =
        1;


    speech.pitch =
        1;


    speech.onstart = () => {

        setBodyState("speaking");
        setSystemStatus("● SPEAKING");

    };


    speech.onend = () => {

        if (
            socket &&
            socket.readyState === WebSocket.OPEN
        ) {

            setBodyState("connected");
            setSystemStatus("● ONLINE");
            setConnectionStatus("CONNECTED");

        }

    };


    speech.onerror = () => {

        if (
            socket &&
            socket.readyState === WebSocket.OPEN
        ) {

            setBodyState("connected");
            setSystemStatus("● ONLINE");
            setConnectionStatus("CONNECTED");

        }

    };


    window.speechSynthesis.speak(
        speech
    );

}
