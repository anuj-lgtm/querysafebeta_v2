document.addEventListener('DOMContentLoaded', function () {
  const counters = document.querySelectorAll('.counter')

  const observerCallback = (entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const counter = entry.target
        const target = parseInt(counter.getAttribute('data-target'))
        const duration = 2000 // 2 seconds
        const steps = 50
        const stepValue = target / steps
        let current = 0

        const updateCounter = () => {
          if (current < target) {
            current += stepValue
            counter.textContent = Math.round(current)
            requestAnimationFrame(updateCounter)
          } else {
            counter.textContent = target
          }
        }

        updateCounter()
        observer.unobserve(counter)
      }
    })
  }

  const observer = new IntersectionObserver(observerCallback, {
    threshold: 0.5
  })

  counters.forEach((counter) => observer.observe(counter))
})

// document.addEventListener('DOMContentLoaded', function () {
//   new Swiper('.swiper-container', {
//     slidesPerView: 1,
//     spaceBetween: 30,
//     centeredSlides: true,
//     loop: true,
//     speed: 800,
//     autoplay: {
//       delay: 5000,
//       disableOnInteraction: false
//     },
//     pagination: {
//       el: '.swiper-pagination',
//       clickable: true
//     },
//     navigation: {
//       prevEl: '.nav-button.prev',
//       nextEl: '.nav-button.next'
//     },
//     breakpoints: {
//       768: {
//         slidesPerView: 2
//       },
//       1200: {
//         slidesPerView: 3
//       }
//     },
//     effect: 'coverflow',
//     coverflowEffect: {
//       rotate: 0,
//       stretch: 0,
//       depth: 100,
//       modifier: 2,
//       slideShadows: false
//     }
//   })
// })

document.addEventListener('DOMContentLoaded', function() {
    // Navbar scroll behavior
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', function() {
        if (window.scrollY > 20) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Toast auto-dismiss
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    });

    // Dropdown hover on desktop
    if (window.innerWidth > 991) {
        const dropdowns = document.querySelectorAll('.dropdown');
        dropdowns.forEach(dropdown => {
            dropdown.addEventListener('mouseenter', function() {
                const dropdownMenu = this.querySelector('.dropdown-menu');
                dropdownMenu.classList.add('show');
            });
            
            dropdown.addEventListener('mouseleave', function() {
                const dropdownMenu = this.querySelector('.dropdown-menu');
                dropdownMenu.classList.remove('show');
            });
        });
    }

    // Close mobile menu on click outside
    document.addEventListener('click', function(event) {
        const navbar = document.querySelector('.navbar-collapse');
        const toggler = document.querySelector('.navbar-toggler');
        
        if (navbar.classList.contains('show') && 
            !navbar.contains(event.target) && 
            !toggler.contains(event.target)) {
            navbar.classList.remove('show');
            toggler.classList.add('collapsed');
            toggler.setAttribute('aria-expanded', 'false');
        }
    });
});

// Show the popup at a specific frequency
document.addEventListener('DOMContentLoaded', function () {
    const popupId = 'promoPopup';
    const popupFrequencyKey = 'promoPopupLastShown';
    const popupFrequencyHours = 24; // Show the popup every 24 hours

    const lastShown = localStorage.getItem(popupFrequencyKey);
    const now = new Date().getTime();

    // Check if the popup should be shown
    if (!lastShown || now - lastShown > popupFrequencyHours * 60 * 60 * 1000) {
        showPromoPopup();
        localStorage.setItem(popupFrequencyKey, now);
    }
});

// Show the popup
function showPromoPopup() {
    const popup = document.getElementById('promoPopup');
    if (popup) {
        popup.classList.remove('d-none');
    }
}

// Close the popup
function closePromoPopup() {
    const popup = document.getElementById('promoPopup');
    if (popup) {
        popup.classList.add('d-none');
    }
}
