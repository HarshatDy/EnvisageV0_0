// Function to load HTML components into the page
// function loadComponent(componentUrl, targetSelector) {
//     return fetch(componentUrl)
//         .then(response => {
//             if (!response.ok) {
//                 throw new Error(`Failed to load component: ${componentUrl}`);
//             }
//             return response.text();
//         })
//         .then(html => {
//             document.querySelector(targetSelector).innerHTML = html;
//             return html;
//         })
//         .catch(error => {
//             console.error('Error loading component:', error);
//         });
// }

// Initialize components when the DOM is fully loaded
// document.addEventListener('DOMContentLoaded', function() {
//     // Load sidebar and header components
//     Promise.all([
//         loadComponent('components/sidebar.html', '#sidebar-container'),
//         loadComponent('components/header.html', '#header-container')
//     ]).then(() => {
//         // Initialize sidebar event handlers
//         initializeSidebar();
        
//         // Create and dispatch a custom event that other scripts can listen for
//         const event = new Event('components-loaded');
//         document.dispatchEvent(event);
//     });
// });

// Function to initialize sidebar event handlers
function initializeSidebar() {
    // Handle sidebar link clicks
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.addEventListener('click', function(e) {
            // If the link is to another page, let it proceed normally
            if (this.getAttribute('href') && this.getAttribute('href') !== '#') {
                return;
            }
            
            // Otherwise prevent default and handle it as a tab change
            e.preventDefault();
            document.querySelectorAll('.sidebar-link').forEach(l => {
                l.classList.remove('is-active');
            });
            this.classList.add('is-active');
        });
    });

    // Handle sidebar collapse for logo click
    document.querySelector('.logo').addEventListener('click', function() {
        document.querySelector('.sidebar').classList.toggle('collapse');
    });
    
    // Handle window resize for responsive sidebar
    function handleResize() {
        if (window.innerWidth > 1090) {
            document.querySelector('.sidebar').classList.remove('collapse');
        } else {
            document.querySelector('.sidebar').classList.add('collapse');
        }
    }
    
    // Initial call and add event listener
    handleResize();
    window.addEventListener('resize', handleResize);
}
