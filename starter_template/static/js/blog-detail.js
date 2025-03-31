$(document).ready(function() {
    // Retrieve parameters from URL
    // const urlParams = new URLSearchParams(window.location.search);
    // const title = urlParams.get('title');
    // const author = urlParams.get('author');
    // const authorImg = urlParams.get('authorImg');
    // const blogImg = urlParams.get('blogImg');

    // If we have parameters in the URL, use them to populate the blog detail page
    if (title) {
        $("#blog-title").text(decodeURIComponent(title));
    }
    if (author) {
        $("#blog-author-name").text(decodeURIComponent(author));
    }
    if (authorImg) {
        $("#blog-author-img").attr("src", decodeURIComponent(authorImg));
    }
    if (blogImg) {
        $("#blog-detail-img").attr("src", decodeURIComponent(blogImg));
    }

    // Handle sidebar functionality
    $(".sidebar-link").click(function () {
        $(".sidebar-link").removeClass("is-active");
        $(this).addClass("is-active");
    });

    // Handle window resize for responsive sidebar
    $(window).resize(function () {
        if ($(window).width() > 1090) {
            $(".sidebar").removeClass("collapse");
        } else {
            $(".sidebar").addClass("collapse");
        }
    }).resize();

    // Add comment button functionality
    $(".chat-footer input").keypress(function(e) {
        if (e.which === 13) {
            const commentText = $(this).val();
            if (commentText.trim() !== '') {
                // Create new comment
                const newComment = `
                <div class="message anim" style="--delay: .1s">
                    <div class="author-img__wrapper blog-author blog-p">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="feather feather-check">
                            <path d="M20 6L9 17l-5-5" />
                        </svg>
                        <img class="author-img" src="https://images.unsplash.com/photo-1587918842454-870dbd18261a?ixlib=rb-1.2.1&ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&auto=format&fit=crop&w=943&q=80" />
                    </div>
                    <div class="msg-wrapper">
                        <div class="msg__name blog-p-name">You</div>
                        <div class="msg__content blog-p-sub">${commentText}</div>
                    </div>
                </div>
                `;
                
                // Add comment to message container
                $(".message-container").append(newComment);
                
                // Clear input
                $(this).val('');
            }
        }
    });
});
