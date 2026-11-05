// Wait for the HTML document to fully load
document.addEventListener("DOMContentLoaded", () => {
    
    // 1. Auto-hide flash messages after 4 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.5s ease";
            alert.style.opacity = "0";
            // Remove the element from the DOM after fading out
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });

    // 2. Add confirmation prompt to the "Confirm Match" buttons
    const matchForms = document.querySelectorAll('form[action*="/admin/match/"]');
    matchForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const confirmAction = confirm("Are you sure you want to confirm this match? This will reserve the item for verification.");
            if (!confirmAction) {
                e.preventDefault(); // Stop the form from submitting if they click "Cancel"
            }
        });
    });

    const returnForms = document.querySelectorAll('form[action*="/admin/return/"]');
    returnForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!confirm("Record this verified handover and mark the item as returned?")) {
                e.preventDefault();
            }
        });
    });

    // 3. Optional: Display selected image file name in the Upload form
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const fileName = e.target.files[0]?.name;
            if (fileName) {
                alert(`Selected image: ${fileName}`);
            }
        });
    }
});