// // static/js/scripts.js

// // Function to show the spinner overlay
// function showSpinner() {
//     document.getElementById('spinner').style.display = 'flex';
// }

// // Function to hide the spinner overlay
// function hideSpinner() {
//     document.getElementById('spinner').style.display = 'none';
// }

// // Function to show the progress bar
// function showProgressBar() {
//     var progressBar = document.getElementById('progressBar');
//     if(progressBar){
//         progressBar.style.display = 'block';
//     }
// }

// // Function to update the progress bar
// function updateProgressBar(percent) {
//     var progressBarFill = document.getElementById('progressBarFill');
//     if(progressBarFill){
//         progressBarFill.style.width = percent + '%';
//         progressBarFill.innerText = percent + '%';
//     }
// }

// // Function to hide the progress bar
// function hideProgressBar() {
//     var progressBar = document.getElementById('progressBar');
//     if(progressBar){
//         progressBar.style.display = 'none';
//     }
// }

// // Dark Mode Toggle Functionality
// document.addEventListener('DOMContentLoaded', function() {
//     const darkModeToggle = document.getElementById('darkModeToggle');
//     if(darkModeToggle){
//         // Check if dark mode was previously enabled
//         if(localStorage.getItem('darkMode') === 'enabled'){
//             document.body.classList.add('dark-mode');
//             darkModeToggle.checked = true;
//         }

//         darkModeToggle.addEventListener('change', function() {
//             if(this.checked){
//                 document.body.classList.add('dark-mode');
//                 localStorage.setItem('darkMode', 'enabled');
//             }
//             else{
//                 document.body.classList.remove('dark-mode');
//                 localStorage.setItem('darkMode', 'disabled');
//             }
//         });
//     }

//     // Form Submission Handling
//     const form = document.querySelector('form');
//     if(form){
//         form.addEventListener('submit', function() {
//             showSpinner();
//             showProgressBar();
//             updateProgressBar(0); // Initialize progress
//         });
//     }
// });

///////////////////////////////////////////////////////////////////////////////////////////////////////////////

// 




// static/js/scripts.js

// Function to show the spinner overlay
function showSpinner() {
    document.getElementById('spinner').style.display = 'flex';
}

// Function to hide the spinner overlay
function hideSpinner() {
    document.getElementById('spinner').style.display = 'none';
}

// Function to show the progress bar
function showProgressBar() {
    var progressBar = document.getElementById('progressBar');
    if(progressBar){
        progressBar.style.display = 'block';
    }
}

// Function to update the progress bar
function updateProgressBar(percent) {
    var progressBarFill = document.getElementById('progressBarFill');
    if(progressBarFill){
        progressBarFill.style.width = percent + '%';
        progressBarFill.innerText = percent + '%';
    }
}

// Function to hide the progress bar
function hideProgressBar() {
    var progressBar = document.getElementById('progressBar');
    if(progressBar){
        progressBar.style.display = 'none';
    }
}

// Dark Mode Toggle Functionality
document.addEventListener('DOMContentLoaded', function() {
    const darkModeToggle = document.getElementById('darkModeToggle');
    if(darkModeToggle){
        // Check if dark mode was previously enabled
        if(localStorage.getItem('darkMode') === 'enabled'){
            document.body.classList.add('dark-mode');
            darkModeToggle.checked = true;
        }

        darkModeToggle.addEventListener('change', function() {
            if(this.checked){
                document.body.classList.add('dark-mode');
                localStorage.setItem('darkMode', 'enabled');
            }
            else{
                document.body.classList.remove('dark-mode');
                localStorage.setItem('darkMode', 'disabled');
            }
        });
    }

    // Form Submission Handling
    const form = document.getElementById('uploadForm');
    if(form){
        form.addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission
            showSpinner();
            updateProgressBar(0); // Initialize progress

            // Create FormData object
            var formData = new FormData(form);

            // Send form data via fetch
            fetch('/', {
                method: 'POST',
                body: formData
            }).then(function(response) {
                if(response.status === 202){
                    // Form submission accepted
                    console.log('Processing started');
                } else {
                    // Form submission failed
                    console.error('Form submission failed');
                    hideSpinner();
                    hideProgressBar();
                    response.text().then(function(text) {
                        displayMessage('danger', text);
                    });
                }
            }).catch(function(error) {
                console.error('Error submitting form:', error);
                hideSpinner();
                hideProgressBar();
                displayMessage('danger', 'Error submitting form. Please try again.');
            });
        });
    }
});

// Function to display messages dynamically
function displayMessage(category, message) {
    var messagesDiv = document.getElementById('messages');
    var alertDiv = document.createElement('div');
    alertDiv.classList.add('alert', `alert-${category}`, 'alert-dismissible', 'fade', 'show');
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    messagesDiv.appendChild(alertDiv);
}

