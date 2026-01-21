document.addEventListener('DOMContentLoaded', () => {
    const WS_URL = "ws://localhost:8000/ws/translate";
    let ws;
    let player;
    let currentMode = "url"
    let selectedFile = null

    let state = {
        language: 'zh',
        context: '',
        subtitles: [],
        isReady: false,
        isStreamRunning: false, 
        currentStreamStart: 0,
        model_size: 'large-v3',
        firstPlay: true,
        url: ""
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
        fsBtn: document.getElementById('fullscreen-btn'),

        urlSection: document.getElementById('url-section'),
        fileSection: document.getElementById('file-section'),
        dropArea: document.getElementById('drop-area'),
        fileInput: document.getElementById('file-input'),
        fileStatus: document.getElementById('file-status'),
        fileNameDisplay: document.getElementById('file-name'),
        removeFileBtn: document.getElementById('remove-file-btn'),
        fileSubmitBtn: document.getElementById('file-submit-button'),
        playerContainer: document.getElementById('player')
    };

    window.switchMode = (mode) => {
        currentMode = mode;
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');

        if (mode === 'url') {
            elements.urlSection.classList.remove('hidden');
            elements.urlSection.style.display = 'flex';
            elements.fileSection.classList.add('hidden');
            elements.fileSection.style.display = 'none';
        }
        else if (mode == 'file') {
            elements.fileSection.classList.remove('hidden');
            elements.fileSection.style.display = 'flex';
            elements.urlSection.classList.add('hidden');
            elements.urlSection.style.display = 'none';
        }
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        elements.dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    elements.dropArea.addEventListener('dragover', () => elements.dropArea.classList.add('dragover'));
    elements.dropArea.addEventListener('dragleave', () => elements.dropArea.classList.remove('dragover'));
    elements.dropArea.addEventListener('drop', handleDrop);
    elements.dropArea.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

    function handleDrop(e) {
        elements.dropArea.classList.remove('dragover');
        const dt = e.dataTransfer;
        handleFiles(dt.files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            selectedFile = files[0];
            elements.fileNameDisplay.innerText = selectedFile.name;
            
            elements.dropArea.classList.add('hidden');
            elements.dropArea.style.display = 'none';
            elements.fileStatus.classList.remove('hidden');
            elements.fileStatus.style.display = 'flex';
            elements.fileSubmitBtn.disabled = false;
        }
    }

    elements.removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFile = null;
        elements.fileInput.value = '';
        
        elements.fileStatus.classList.add('hidden');
        elements.fileStatus.style.display = 'none';
        elements.dropArea.classList.remove('hidden');
        elements.dropArea.style.display = 'flex';
        elements.fileSubmitBtn.disabled = true;
    });


    function setupHtml5Player(fileUrl) {
        const container = document.querySelector('.video-wrapper');

        const overlay = document.getElementById('subtitle-overlay');
        const fsBtn = document.getElementById('fullscreen-btn');
        container.innerHTML = ''; 
        
        const video = document.createElement('video');
        video.id = 'player';
        video.src = fileUrl;
        video.controls = true;
        video.style.width = '100%';
        video.style.height = '100%';
        video.style.backgroundColor = '#000';
        
        container.appendChild(video);
        container.appendChild(overlay);
        container.appendChild(fsBtn);   

        player = {
            getCurrentTime: () => video.currentTime,
            pauseVideo: () => video.pause(),
            playVideo: () => video.play(),

            getPlayerState: () => {
                if (video.paused) return 2; 
                if (video.ended) return 0;  
                return 1;
            }
        };

        video.addEventListener('play', () => onPlayerStateChange({ data: 1 }));
        video.addEventListener('pause', () => onPlayerStateChange({ data: 2 }));
        video.addEventListener('seeking', () => onPlayerStateChange({ data: 3 }));
    }


    elements.fileSubmitBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        setUiLock(true);
        updateStatus("Uploading video to AI server...");

        const localVideoUrl = URL.createObjectURL(selectedFile);
        setupHtml5Player(localVideoUrl);

        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('http://localhost:8000/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.status === 'success') {
                updateStatus("Processing audio...");
                
                state.url = "local_file";
                state.isReady = false;
                resetStreamState();

                ws.send(JSON.stringify({
                    action: "load_file",
                    file_path: result.file_path,
                    language: state.language,
                    context: state.context,
                    model_size: state.model_size,
                    timestamp: 0.0
                }));
            } else {
                alert("Upload failed: " + result.message);
                setUiLock(false);
            }

        } catch (error) {
            console.error(error);
            alert("Error uploading file");
            setUiLock(false);
        }
    });

    function setUiLock(locked) {
        if (locked) {
            elements.loadBtn.disabled = true;
            elements.loadBtn.innerText = "PROCESSING...";
            elements.loadBtn.style.opacity = "0.5";
            elements.sidePanel.classList.add('ui-disabled');
            elements.videoWrapper.classList.add('ui-disabled');
            elements.contextBtn.disabled = true;
            elements.contextBtn.classList.add('ui-disabled');

            if (player) player.pauseVideo();

            elements.subtitleText.innerText = "[SYSTEM] Processing... Please wait.";
        } else {
            elements.loadBtn.disabled = false;
            elements.loadBtn.innerText = "INITIALIZE VIDEO";
            elements.loadBtn.style.opacity = "1";
            elements.sidePanel.classList.remove('ui-disabled');
            elements.videoWrapper.classList.remove('ui-disabled');
            elements.contextBtn.disabled = false;
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
        ws.onopen = () => { 
            updateStatus("AI Connected. Ready to load.");
            getInitialConfig()
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.status) {
                updateStatus(data.status);

                if (data.status === "Ready to play") {
                    state.isReady = true;
                    state.model_size = data.model_size

                    if (state.firstPlay) {
                        // unlock ui after loading model
                        setUiLock(true);
                        updateStatus("Buffering AI Stream (5 seconds)...")
                    }
                    else {
                        setUiLock(false);
                        updateStatus("Ready to play");
                    }
                }


                else if (data.status === "Started translation") {
                    state.isStreamRunning = true;
                    console.log(`New translation stream started in backend ${data}`)
                    updateStatus("Buffering AI Stream for subtitles (5 seconds)...")
                }


                else if (data.status === "New Model Ready") {
                    state.model_size = data.model_size;
                    updateStatus("Successfully changed model. Buffering AI Stream (5 seconds)...");
                }

                else if (data.status === "Failed to change Model size") {
                    updateStatus("Failed to change model.");

                    // revert UI only
                    elements.modelSelect.value = data.model_size

                    // reset playback state safely
                    state.subtitles = [];
                    state.firstPlay = true;
                }


                else if (data.status === "Language Changed") {
                    state.language = data.language
                    updateStatus("Changed language successfully. Buffering AI Stream (5 seconds)...")
                }


                else if (data.status === "Context Changed") {
                    state.context = data.context
                    updateStatus("Changed context successfully. Buffering AI Stream (5 seconds)...")
                }
            }


            else if (data.type === 'config') {
                updateStatus("Received init config")
                console.log(`Default model size ${state.model_size} init model size ${data.model_size}`)
                state.model_size = data.model_size
                elements.modelSelect.value = state.model_size
                // elements.modelSelect.text = state.model_size
                setUiLock(false);
            }


            else if (data.type === "silence") {
                state.isStreamRunning = false;

                state.subtitles.push({
                    start: data.start,
                    end: data.end,
                    text: "" // explicit silence marker
                });
                
                if (state.firstPlay) {
                    if (data.start >= 10) {
                        setUiLock(false);
                        state.firstPlay = false;
                    }
                }
            }

            
            // This is where we unlock the ui for any changed that happened while the
            // model is running
            else if (data.type && data.type === "subtitle") {
                if (!state.isReady) return

                // if (state.firstPlay) {
                //         setUiLock(true)
                //         updateStatus("[SYSTEM] Buffering AI Stream")
                //     }

                if (data.language != state.language) {
                    console.log(`Current lang is ${state.language} but revcieved sub for ${data.language}. Discarded sub`)
                    return
                }
                else if (data.language === state.language) {
                    if (!state.subtitles.find(sub => sub.start == data.start)) {
                        state.subtitles.push(data)
                        console.log(`Received subtitle: [${data.start.toFixed(2)}s - ${data.end.toFixed(2)}s] ${data.text}`);
                    }

                    if (state.firstPlay && state.subtitles.length > 0) {
                        console.log("Initial subtitles received. Unlocking UI.");
                        setUiLock(false)
                        updateStatus("[SYSTEM] Subtitle Received, Ready To Play!")
                        state.firstPlay = false
                    }
                }

            }
        }
        ws.onclose = () => { setTimeout(connectWebSocket, 3000); };
    }

    function resetStreamState() {
        state.isStreamRunning = false;
        state.subtitles = [];
        state.firstPlay = true;
    }

    function debounce(fn, delay = 500) {
        let timer = null;

        return function (...args) {
            const context = this;

            clearTimeout(timer);
            timer = setTimeout(() => {
            fn.apply(context, args);
            }, delay);
        };
    }

    function hasData(timestamp) {
        // return state.subtitles.some(sub => sub.start <= timestamp &&  sub.end >= timestamp) // old logic

        // new logic
        if (state.subtitles && state.subtitles.length >= 1) {
            const max_start = Math.max(...state.subtitles.map(s => s.start));
            if (max_start >= timestamp) {
                // the backend has already processed past this point
                // if there are no sub them it must have been silence
                return true
            }
            return false
        }
        return false
    }

    const debouncedStartStream = debounce((timestamp) => {
        if (state.isStreamRunning) {
            console.log("Stream already running (silence or speech)");
            return;
        }
        

        if (hasData(timestamp)) {
            console.log(`Cache Hit at ${timestamp}s. Playing from memory.`);
            return
        }

        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        setUiLock(true) // wait for subtitle to come
        ws.send(JSON.stringify({
            action : "translate",
            timestamp : timestamp
        }))

        // this only trigger when skip ahead of backend
        console.log(`Cache Miss at ${timestamp}s. Requesting Stream...`);
        state.isStreamRunning = true;
    }, 400);



    elements.modelSelect.addEventListener("change", () => {
        if (elements.modelSelect.value !== state.model_size) {
            // call backend only when the video has been loaded
            if (state.url) {
                setUiLock(true);
                ws.send(JSON.stringify({
                    action: "change_model",
                    timestamp : player.getCurrentTime(),
                    model_size: elements.modelSelect.value
                }));

                state.isReady = false;
                resetStreamState();
            }
            else {
                state.model_size = elements.modelSelect.value
            }
        }
    });



    elements.langButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            if (elements.sidePanel.classList.contains('ui-disabled')) return;

            document.querySelector('.language-button.active')?.classList.remove('active');
            btn.classList.add('active');

            const new_language = btn.value
            if (state.language === new_language) return;

            if (state.url) {
                setUiLock(true)
                ws.send(JSON.stringify({
                    action: "change_language",
                    language: new_language,
                    timestamp: player.getCurrentTime()
                }))

                resetStreamState();
            }
            else {
                state.language = new_language
            }
        })
    })



    elements.contextBtn.addEventListener("click", () => {
        const new_context = elements.contextInput.value
        if (new_context == state.context) return
        
        if (state.url) {
            setUiLock(true)

            ws.send(JSON.stringify({
                action : "change_context",
                context : new_context,
                timestamp : player.getCurrentTime()
            }));

            resetStreamState();
        }
        else {
            state.context = new_context
        }
        
    });



    function restoreYouTubePlayer() {
        if (player && typeof player.cueVideoById === 'function') return;

        console.log("Restoring YouTube Player...");
        
        const container = document.querySelector('.video-wrapper');
        const overlay = document.getElementById('subtitle-overlay');
        const fsBtn = document.getElementById('fullscreen-btn');

        container.innerHTML = '<div id="player"></div>'; 
        container.appendChild(overlay);
        container.appendChild(fsBtn);

        player = new YT.Player('player', {
            height: '100%', width: '100%',
            playerVars: { 'playsinline': 1, 'fs': 0, 'controls': 1 },
            events: { 'onStateChange': onPlayerStateChange }
        });
    }

    elements.loadBtn.addEventListener('click', () => {
        if (currentMode !== 'url') return;

        restoreYouTubePlayer()

        const url = elements.urlInput.value;
        const match = url.match(/(?:v=|\/)([\w-]{11})/);

        if (!match) {
            elements.urlInput.value = "Invalid URL"
            return
        }

        setTimeout(() => {
            if (!player || typeof player.cueVideoById !== 'function') {
                alert("YouTube Player is loading... click again in a second.");
                return;
            }

            setUiLock(true);
            ws.send(JSON.stringify({
                action : "load_video",
                url : url,
                language : state.language,
                context : state.context,
                model_size : state.model_size,
                timestamp : 0.0
            }));
            
            resetStreamState();
            state.isReady = false;
            state.currentStreamStart = 0;
            state.url = url;

            player.cueVideoById(match[1]);
        }, 100);
    })


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
            player.pauseVideo()
            return
        }

        if (event.data === YT.PlayerState.PLAYING) {
            const t = player.getCurrentTime()
            debouncedStartStream(t)
        }

        else if (event.data === YT.PlayerState.BUFFERING) {
            const t = player.getCurrentTime()
            debouncedStartStream(t)
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


    function getInitialConfig() {
        setUiLock(true)

        ws.send(JSON.stringify({
            action : "init_config"
        }))
    }
    connectWebSocket();
});