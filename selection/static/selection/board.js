(function () {
    var CONFETTI_COLORS = ["#e74c3c", "#27ae60", "#f5a623", "#1f3b73", "#9b59b6", "#2f6fed"];

    function spawnConfetti(container, count) {
        var layer = document.createElement("div");
        layer.className = "confetti-layer";
        container.appendChild(layer);

        for (var i = 0; i < count; i++) {
            var piece = document.createElement("div");
            piece.className = "confetti-piece";
            piece.style.left = Math.random() * 100 + "%";
            piece.style.background = CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)];
            piece.style.animationDuration = (0.9 + Math.random() * 0.9) + "s";
            piece.style.animationDelay = (Math.random() * 0.3) + "s";
            layer.appendChild(piece);
        }

        setTimeout(function () {
            layer.remove();
        }, 2200);
    }

    function runRevealAnimation(card) {
        if (card._revealInterval) {
            clearInterval(card._revealInterval);
            card._revealInterval = null;
        }

        var nameEl = card.querySelector(".reveal-name");
        var finalName = nameEl.getAttribute("data-final-name");
        var candidatesRaw = card.getAttribute("data-candidates") || "";
        var candidates = candidatesRaw.split("|").filter(Boolean);

        if (candidates.length > 1) {
            nameEl.classList.add("cycling");
            var cycles = 10;
            var i = 0;
            card._revealInterval = setInterval(function () {
                nameEl.textContent = candidates[Math.floor(Math.random() * candidates.length)];
                i++;
                if (i >= cycles) {
                    clearInterval(card._revealInterval);
                    card._revealInterval = null;
                    nameEl.textContent = finalName;
                    nameEl.classList.remove("cycling");
                    revealCard(card);
                }
            }, 90);
        } else {
            nameEl.textContent = finalName;
            revealCard(card);
        }
    }

    function revealCard(card) {
        card.classList.remove("pop");
        void card.offsetWidth;
        card.classList.add("pop");
        spawnConfetti(card, 28);
    }

    document.addEventListener("DOMContentLoaded", function () {
        var card = document.querySelector(".reveal-card[data-animate='true']");
        if (card) {
            runRevealAnimation(card);
        }
    });

    window.BoardReveal = { run: runRevealAnimation, confetti: spawnConfetti };
})();
