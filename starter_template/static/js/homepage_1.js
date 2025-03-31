$(function () {
    $(".sidebar-link").click(function () {
     $(".sidebar-link").removeClass("is-active");
     $(this).addClass("is-active");
    });
   });
   
   $(window)
    .resize(function () {
     if ($(window).width() > 1090) {
      $(".sidebar").removeClass("collapse");
     } else {
      $(".sidebar").addClass("collapse");
     }
    })
    .resize();
   
   const allBlogs = document.querySelectorAll(".blog");
   
//    allBlogs.forEach((v) => {
//     v.addEventListener("mouseover", () => {
//      const blog = v.querySelector("video");
//      if (blog) blog.play();
//     });
//     v.addEventListener("mouseleave", () => {
//      const blog = v.querySelector("video");
//      if (blog) blog.pause();
//     });
//    });
   
   $(function () {
    $(".logo, .logo-expand, .discover").on("click", function (e) {
     $(".main-container").removeClass("show");
     $(".main-container").scrollTop(0);
    });
    $(".trending").on("click", function (e) {
     $(".main-container").addClass("show");
     $(".main-container").scrollTop(0);
     $(".sidebar-link").removeClass("is-active");
     $(".trending").addClass("is-active");
    });
   
    // $(".blog").click(function () {
    //  var source = $(this).find("source").attr("src");
    //  var title = $(this).find(".blog-name").text();
    //  var person = $(this).find(".blog-by").text();
    //  var img = $(this).find(".author-img").attr("src");
    //  $(".blog-stream video").stop();
    //  $(".blog-stream source").attr("src", source);
    //  $(".blog-stream video").load();
    //  $(".blog-p-title").text(title);
    //  $(".blog-p-name").text(person);
    //  $(".blog-detail .author-img").attr("src", img);
    // });
    
    // Fix for scrollable menus - this ensures scrollbars appear when needed
    function adjustSideMenuHeight() {
      $('.side-menu').each(function() {
        const menuItems = $(this).children('a').length;
        if (menuItems > 4) {
          $(this).css('overflow-y', 'auto');
        } else {
          $(this).css('overflow-y', 'hidden');
        }
      });
    }
    
    // Run on page load
    adjustSideMenuHeight();
    
    // Also run on window resize
    $(window).resize(function() {
      adjustSideMenuHeight();
    });
   });
