document.addEventListener('DOMContentLoaded', () => {
    const WS_URL = "ws://localhost:8000/ws/translate";
    let ws;
    let player;
    let debounceTimer;

    let state = {
        language: 'zh',
        context: '',
        subtitles: [],
        isReady: false,
        isStreamRunning: false, 
        currentStreamStart: 0,
        firstPlay: true,
    };

    const elements = {
        urlInput: document.getElementById('video-url'),
        loadBtn: document.getElementById('url-submit-button'),
        contextInput: document.getElementById('context-input'),
        contextBtn: document.getElementById('context-set-button'),
        subtitleText: document.getElementById('subtitle-text'),
        langButtons: document.querySelectorAll('.language-button'),
        modelSelect: document.getElementById('model-select'),
        sidePanel: document.querySelector('.side-panel'),
        videoWrapper: document.querySelector('.video-wrapper'),
        fsBtn: document.getElementById('fullscreen-btn')
    };

    function setUiLock(locked) {
        if (locked) {
            elements.loadBtn.disabled = true;
            elements.loadBtn.innerText = "PROCESSING...";
            elements.loadBtn.style.opacity = "0.5";
            elements.sidePanel.classList.add('ui-disabled');
            elements.videoWrapper.classList.add('ui-disabled');
            elements.contextBtn.classList.add('ui-disabled');
            elements.subtitleText.innerText = "[SYSTEM] Processing... Please wait.";
        } else {
            elements.loadBtn.disabled = false;
            elements.loadBtn.innerText = "INITIALIZE VIDEO";
            elements.loadBtn.style.opacity = "1";
            elements.sidePanel.classList.remove('ui-disabled');
            elements.videoWrapper.classList.remove('ui-disabled');
            elements.contextBtn.classList.remove('ui-disabled');
        }
    }

    function updateStatus(message) {
        if (!message.includes("Waiting") || elements.subtitleText.innerText.includes("[SYSTEM]")) {
            elements.subtitleText.innerText = `[SYSTEM] ${message}`;
            elements.subtitleText.style.color = '#eeeeee';
        }
    }

    function connectWebSocket() {
        ws = new WebSocket(WS_URL);
        ws.onopen = () => { updateStatus("AI Connected. Ready to load."); };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status) {
                updateStatus(data.status);
                
                if (data.status.includes("Ready")) {
                    state.isReady = true;
                    console.log(`Model Size: ${data.model_size}, Language: ${state.language}`);
                    
                    if (data.status === "Ready to play") {
                       // Backend has auto-started. We just wait for data now.
                       if (state.firstPlay) {
                           setUiLock(true);
                           updateStatus("Buffering AI Stream (~5s)...");
                       } else {
                           setUiLock(false);
                           updateStatus("Ready! Click Play.");
                       }
                    } else {
                        setUiLock(false); 
                    }
                }
            }
            else if (data.type == 'subtitle') {
                if (data.language != state.language && state.firstPlay == true) {
                    console.log(`Discarded subtitle for ${data.language}, current language is ${state.language}`);
                    setUiLock(true);
                    updateStatus("Buffering AI Stream (~5s)...");
                    return;
                }
                if (data.language === state.language && state.firstPlay == true) {
                    console.log(`Received first subtitle for ${data.language}, current language is ${state.language}`);
                    setUiLock(false);
                    updateStatus("Ready! Click Play.");
                    state.firstPlay = false;
                }

                if (!state.isReady) return;
                if (!state.subtitles.find(s => s.start == data.start)) {
                    state.subtitles.push(data);
                    console.log(`Received subtitle: [${data.start.toFixed(2)}s - ${data.end.toFixed(2)}s] ${data.text}`);
                }

                if (state.firstPlay && state.subtitles.length > 0) {
                    console.log("Initial subtitles received. Unlocking UI.");
                    state.firstPlay = false; 
                    setUiLock(false); 
                    updateStatus("Ready! Click Play."); 
                }
            }
        };

        ws.onclose = () => { setTimeout(connectWebSocket, 3000); };
    }

    function isDataCached(time) {
        return state.subtitles.some(s => time >= s.start && time <= s.end)
    }

    function startStream(timestamp) {
        if (!state.isReady) return;

        if (isDataCached(timestamp)) {
            console.log(`Cache Hit at ${timestamp}s. Playing from memory.`);
            state.isStreamRunning = false; 
            return;
        }

        console.log(`Cache Miss at ${timestamp}s. Requesting Stream...`);
        state.isStreamRunning = true;
        state.currentStreamStart = timestamp; 

        ws.send(JSON.stringify({
            action: "translate",
            url: elements.urlInput.value,
            language: state.language,
            context: state.context,
            timestamp: timestamp
        }));
    }

    function handleSeek() {
        if (!player) return;
        const t = player.getCurrentTime();
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            startStream(t);
        }, 300);
    }

    elements.loadBtn.addEventListener('click', () => {
        const url = elements.urlInput.value;
        const match = url.match(/(?:v=|\/)([\w-]{11})/);
        if (match) { 
            ws.send(JSON.stringify({ 
                action: "load_video", 
                url: url,
                language: state.language,
                context: state.context,
                timestamp: 0 
            }));

            setUiLock(true);
            state.isReady = false; 
            state.subtitles = [];
            state.firstPlay = true;
            state.currentStreamStart = 0;
            
            player.cueVideoById(match[1]);
        } else {
            alert("Invalid YouTube URL");
        }
    });

    elements.modelSelect.addEventListener('change', () => {
        setUiLock(true);
        state.isReady = false;
        ws.send(JSON.stringify({ action: "change_model", model_size: elements.modelSelect.value }));
    });
    
    elements.langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (elements.sidePanel.classList.contains('ui-disabled')) return;

            document.querySelector('.language-button.active')?.classList.remove('active');
            btn.classList.add('active');
            state.language = btn.value;
            state.subtitles = [];
            state.firstPlay = true;
            
            if (player.getPlayerState() === YT.PlayerState.PLAYING) {
                handleSeek();
            }
        });
    });

    elements.contextBtn.addEventListener('click', () => {
        state.context = elements.contextInput.value;
        handleSeek(); 
    });

    elements.fsBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            elements.videoWrapper.requestFullscreen().catch(err => {
                alert(`Error enabling full-screen: ${err.message}`);
            });
        } else {
            document.exitFullscreen();
        }
    });

    window.onYouTubeIframeAPIReady = function() {
        player = new YT.Player('player', {
            height: '100%', width: '100%',
            playerVars: { 
                'playsinline': 1, 
                'fs': 0,       
                'controls': 1 
            },
            events: { 'onStateChange': onPlayerStateChange }
        });
    }

    function onPlayerStateChange(event) {
        if (event.data === YT.PlayerState.PLAYING && !state.isReady) {
            player.pauseVideo();
            return;
        }

        if (event.data === YT.PlayerState.PLAYING) {
            const t = player.getCurrentTime();
            startStream(t);
        }
        else if (event.data === YT.PlayerState.BUFFERING) {
            handleSeek();
        }
    }

    setInterval(() => {
        if (!player || !player.getCurrentTime) return;
        const t = player.getCurrentTime();
        const activeSub = state.subtitles.find(s => t >= s.start && t <= s.end);
        
        if (activeSub) {
            if (activeSub.text !== elements.subtitleText.innerText) {
                elements.subtitleText.innerText = activeSub.text;
                elements.subtitleText.style.color = "#eeee";
                document.getElementById('subtitle-overlay').style.opacity = 1;
            }
        } else if (!elements.subtitleText.innerText.includes("SYSTEM")) {
            elements.subtitleText.innerText = "";
        }
    }, 100);

    const list = document.getElementById('language-list');
    document.getElementById('scroll-up').addEventListener('click', () => list.scrollBy({top:-100, behavior:'smooth'}));
    document.getElementById('scroll-down').addEventListener('click', () => list.scrollBy({top:100, behavior:'smooth'}));

    connectWebSocket();
});