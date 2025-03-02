/**
 * This script fixes the sidebar scrolling behavior
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get all side menus
    const sideMenus = document.querySelectorAll('.side-menu');
    
    // Process each side menu separately
    sideMenus.forEach(menu => {
        // Count visible menu items
        const menuItems = menu.querySelectorAll('a');
        
        // If more than 4 items, ensure scrolling is enabled
        if (menuItems.length > 4) {
            // Force the overflow to be visible
            menu.style.overflowY = 'auto';
            menu.style.height = '140px';
            
            // Add extra items to ensure scrolling
            if (menuItems.length === 5) {
                // Add a bit of padding at the bottom to ensure scrollbar appears
                const paddingElement = document.createElement('div');
                paddingElement.style.height = '10px';
                paddingElement.style.flexShrink = '0';
                menu.appendChild(paddingElement);
            }
        } else {
            // If 4 or fewer items, no need for scrolling
            menu.style.overflowY = 'visible';
            menu.style.height = 'auto';
        }
    });
    
    // Add hover effect to improve scrollbar visibility
    sideMenus.forEach(menu => {
        menu.addEventListener('mouseenter', function() {
            this.classList.add('hover-active');
        });
        
        menu.addEventListener('mouseleave', function() {
            this.classList.remove('hover-active');
        });
    });
});
