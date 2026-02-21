document.addEventListener("DOMContentLoaded", () => {
    const container = document.querySelector(".container");
    const btnSignIn = document.getElementById("btn-sign-in");
    const btnSignUp = document.getElementById("btn-sign-up");

    // Lógica para el intercambio de paneles (Animación)
    if (btnSignIn && btnSignUp && container) {
        btnSignIn.addEventListener("click", () => {
            container.classList.remove("toggle");
        });

        btnSignUp.addEventListener("click", () => {
            container.classList.add("toggle");
        });
    } else {
        console.error("Error: Elementos de animación no encontrados. Revisa los IDs.");
    }
});