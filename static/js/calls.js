document.addEventListener('DOMContentLoaded', () => {
    const localVideo = document.getElementById('localVideo');
    const callEmpty = document.getElementById('callEmpty');
    const micToggle = document.getElementById('micToggle');
    const cameraToggle = document.getElementById('cameraToggle');
    const startCamera = document.getElementById('startCamera');
    const endCall = document.getElementById('endCall');
    let localStream = null;

    async function ensureStream() {
        if (localStream) {
            return localStream;
        }
        try {
            localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            localVideo.srcObject = localStream;
            localVideo.style.display = 'block';
            callEmpty.style.display = 'none';
            return localStream;
        } catch (error) {
            return null;
        }
    }

    function stopStream() {
        if (!localStream) {
            return;
        }
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
        localVideo.srcObject = null;
        localVideo.style.display = 'none';
        callEmpty.style.display = 'grid';
        micToggle.textContent = 'Mute Mic';
        cameraToggle.textContent = 'Hide Camera';
    }

    startCamera?.addEventListener('click', () => {
        ensureStream();
    });

    micToggle?.addEventListener('click', async () => {
        const stream = await ensureStream();
        if (!stream) {
            return;
        }
        const track = stream.getAudioTracks()[0];
        if (!track) {
            return;
        }
        track.enabled = !track.enabled;
        micToggle.textContent = track.enabled ? 'Mute Mic' : 'Unmute Mic';
    });

    cameraToggle?.addEventListener('click', async () => {
        const stream = await ensureStream();
        if (!stream) {
            return;
        }
        const track = stream.getVideoTracks()[0];
        if (!track) {
            return;
        }
        track.enabled = !track.enabled;
        cameraToggle.textContent = track.enabled ? 'Hide Camera' : 'Show Camera';
    });

    endCall?.addEventListener('click', () => {
        stopStream();
        window.history.back();
    });

    ensureStream();
});
