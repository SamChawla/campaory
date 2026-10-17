import { Link } from "react-router-dom";

export function Privacy() {
  return (
    <section className="narrow">
      <h1>Privacy note</h1>
      <p>As a guest, your campaign is kept in this browser only. Campaory's server does not store it.</p>
      <p>
        To write posts, the facts you confirmed and the post text are sent to the writing model. Nothing is kept on our server
        from those requests.
      </p>
      <p>If you sign in, we store your name, email and the campaigns you save. No passwords. You can delete a campaign or your whole account at any time.</p>
      <Link to="/" className="btn btn-primary">
        Back to start
      </Link>
    </section>
  );
}
