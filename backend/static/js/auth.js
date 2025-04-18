document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    const data = await response.json();
    const messageEl = document.getElementById('message');
    messageEl.textContent = data.message;
    if (response.ok) {
        messageEl.classList.remove('text-red-500');
        messageEl.classList.add('text-green-500');
        window.location.href = data.role === 'admin' ? '/teacher_home' : '/student_home';
    }
});