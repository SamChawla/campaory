import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <section className="narrow">
      <h1>Page not found</h1>
      <p>That page does not exist. Your campaign on this device is untouched.</p>
      <Link to="/" className="btn btn-primary">
        Back to start
      </Link>
    </section>
  );
}
