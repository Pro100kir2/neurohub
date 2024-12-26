import React from 'react';
import '/Users/pro100kir2/PycharmProjects/NeuroHub/static/styles/main.css'; // Подключение стилей

function AboutPage() {
  return (
    <div className="container">
      <h1>About Us</h1>
      <p>
        Welcome to NeuroHub! We're at the forefront of cutting-edge technologies and artificial intelligence.
        Our mission is to bring advanced AI tools to everyone, enabling creativity, efficiency, and innovation at your fingertips.
      </p>
      <p>
        Whether you're looking to generate your resume, create unique vector images, or even design custom avatars,
        our platform provides the tools you need to unlock your potential. We believe in making AI accessible to all,
        giving you the freedom to explore and create like never before.
      </p>
      <div className="buttons">
        <a href="/register">
          <button>Start Now</button>
        </a>
      </div>
      <div className="links">
        <a href="/templates/about-page">About</a> | <a href="/privacy-policy">Privacy Policy</a>
      </div>
    </div>
  );
}

export default AboutPage;
