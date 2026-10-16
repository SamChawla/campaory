import { Link } from "react-router-dom";

export function Nav() {
  return (
    <header className="nav-wrap">
      <nav className="nav" aria-label="Main">
        <Link to="/" className="nav-logo" aria-label="Campaory home">
          <span className="nav-mark" aria-hidden="true" />
          Campaory
        </Link>
        <Link to="/#start" className="btn btn-highlight nav-cta">
          Try a sample event
        </Link>
      </nav>
    </header>
  );
}
