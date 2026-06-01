// Chain Premium Profile JS

document.addEventListener('DOMContentLoaded', () => {
    console.log("Chain Profile System Initialized");

    // Animate progress bars on load
    const progressFills = document.querySelectorAll('.progress-fill');
    progressFills.forEach(fill => {
        const width = fill.style.width;
        fill.style.width = '0';
        setTimeout(() => {
            fill.style.width = width;
        }, 300);
    });

    // Image Upload Previews
    const setupPreview = (inputSelector, previewSelector) => {
        const input = document.querySelector(inputSelector);
        const preview = document.querySelector(previewSelector);
        if (input && preview) {
            input.addEventListener('change', function() {
                const file = this.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        if (preview.tagName === 'IMG') {
                            preview.src = e.target.result;
                        } else {
                            preview.style.backgroundImage = `url(${e.target.result})`;
                        }
                    }
                    reader.readAsDataURL(file);
                }
            });
        }
    };

    setupPreview('input[name="avatar"]', '.avatar-inner img');
    setupPreview('input[name="cover"]', '.cover-img');
});

function toggleFollow(profileId, action) {
    const url = `/profile/${profileId}/follow`;
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.reload();
        } else {
            alert(data.message || 'Action failed.');
        }
    })
    .catch(err => {
        console.error('Engagement error:', err);
    });
}
