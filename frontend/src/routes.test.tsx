import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./routes";

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
}

test("start screen renders the promise and the sample action", () => {
  renderAt("/");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/event promotion/i);
  expect(screen.getAllByRole("link", { name: /try a sample event/i }).length).toBeGreaterThan(0);
});

test("nav is present with the brand", () => {
  renderAt("/");
  expect(screen.getByRole("navigation", { name: /main/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /campaory home/i })).toBeInTheDocument();
});

test("unknown route shows a way back", () => {
  renderAt("/nowhere");
  expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /back to start/i })).toHaveAttribute("href", "/");
});

test("start screen explains the four steps and where guest work is kept", () => {
  renderAt("/");
  expect(screen.getByRole("heading", { name: /how it works/i })).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getByText(/stays in this browser until you sign in/i)).toBeInTheDocument();
});
