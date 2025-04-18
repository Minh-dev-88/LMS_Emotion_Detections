const videoGrid = document.getElementById('video-grid');
const toggleVideoBtn = document.getElementById('toggle-video');
const toggleAudioBtn = document.getElementById('toggle-audio');
const shareScreenBtn = document.getElementById('share-screen');
const leaveMeetingBtn = document.getElementById('leave-meeting');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat');

let myPeer = new Peer(undefined, {
    host: 'peerjs-server.herokuapp.com',
    secure: true,
    port: 443
});
let myStream;
let myScreenStream;
let peers = {};

navigator.mediaDevices.getUserMedia({
    video: true,
    audio: true
}).then(stream => {
    myStream = stream;
    const myVideo = document.createElement('video');
    myVideo.muted = true;
    addVideoStream(myVideo, stream);

    myPeer.on('call', call => {
        call.answer(stream);
        const video = document.createElement('video');
        call.on('stream', userVideoStream => {
            addVideoStream(video, userVideoStream);
        });
        peers[call.peer] = call;
    });

    myPeer.on('open', id => {
        const roomId = `room_${classId}`;
        fetch('/join_room', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_id: roomId, peer_id: id })
        }).then(() => {
            connectToNewUser(id, stream);
        });
    });

    // Chat functionality
    sendChatBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Toggle video
    let videoEnabled = true;
    toggleVideoBtn.addEventListener('click', () => {
        videoEnabled = !videoEnabled;
        myStream.getVideoTracks()[0].enabled = videoEnabled;
        toggleVideoBtn.textContent = videoEnabled ? 'Tắt Video' : 'Bật Video';
    });

    // Toggle audio
    let audioEnabled = true;
    toggleAudioBtn.addEventListener('click', () => {
        audioEnabled = !audioEnabled;
        myStream.getAudioTracks()[0].enabled = audioEnabled;
        toggleAudioBtn.textContent = audioEnabled ? 'Tắt Âm thanh' : 'Bật Âm thanh';
    });

    // Share screen
    shareScreenBtn.addEventListener('click', () => {
        navigator.mediaDevices.getDisplayMedia({
            video: true
        }).then(screenStream => {
            myScreenStream = screenStream;
            const screenVideo = document.createElement('video');
            screenVideo.classList.add('screen-share');
            addVideoStream(screenVideo, screenStream);
            screenStream.getVideoTracks()[0].onended = () => {
                screenVideo.remove();
            };
        });
    });

    // Leave meeting
    leaveMeetingBtn.addEventListener('click', () => {
        window.location.href = role === 'admin' ? '/teacher_home?section=home' : '/student_home';
    });
}).catch(err => {
    console.error("Error accessing media devices:", err);
});

function addVideoStream(video, stream) {
    video.srcObject = stream;
    video.addEventListener('loadedmetadata', () => {
        video.play();
    });
    videoGrid.append(video);
}

function connectToNewUser(userId, stream) {
    const call = myPeer.call(userId, stream);
    const video = document.createElement('video');
    call.on('stream', userVideoStream => {
        addVideoStream(video, userVideoStream);
    });
    call.on('close', () => {
        video.remove();
    });
    peers[userId] = call;
}

function sendMessage() {
    const message = chatInput.value.trim();
    if (message) {
        const msgElement = document.createElement('p');
        msgElement.textContent = `${userName}: ${message}`;
        chatMessages.appendChild(msgElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        chatInput.value = '';
        // Gửi tin nhắn qua PeerJS (có thể mở rộng nếu cần)
    }
}