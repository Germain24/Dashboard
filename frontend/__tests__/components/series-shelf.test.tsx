import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Book } from "@/lib/livres";
import { SeriesShelf } from "@/components/livres/SeriesShelf";

const book = (over: Partial<Book>): Book => ({
  id: 1, titre: "T", auteur: "A", isbn: null, pages: 200, statut: "a_lire",
  genre: "", langue: "", format: "papier", note: null, page_courante: null,
  date_debut: null, date_fin: null, couverture_url: null, serie: "", tome: null,
  ...over,
})

const renderBook = (b: Book) => <span>{b.titre}</span>

describe("SeriesShelf", () => {
  it("regroupe les tomes sous leur serie, tries, avec la progression", () => {
    render(
      <SeriesShelf
        books={[
          book({ id: 2, titre: "OP 2", serie: "One Piece", tome: 2 }),
          book({ id: 1, titre: "OP 1", serie: "One Piece", tome: 1, statut: "lu" }),
        ]}
        renderBook={renderBook}
      />,
    );
    expect(screen.getByText("One Piece")).toBeInTheDocument();
    expect(screen.getByText("1/2 tomes lus")).toBeInTheDocument();
    const tomes = screen.getAllByText(/^T\d+$/).map((e) => e.textContent);
    expect(tomes).toEqual(["T1", "T2"]);
  });

  it("ignore les livres isoles (sans serie)", () => {
    render(<SeriesShelf books={[book({ titre: "Sapiens" })]} renderBook={renderBook} />);
    expect(screen.queryByText("Sapiens")).not.toBeInTheDocument();
  });

  it("tolere un tome sans numero", () => {
    render(
      <SeriesShelf
        books={[
          book({ id: 1, titre: "Gunnm HS", serie: "Gunnm", tome: null }),
          book({ id: 2, titre: "Gunnm 1", serie: "Gunnm", tome: 1 }),
        ]}
        renderBook={renderBook}
      />,
    );
    expect(screen.getByText("Gunnm")).toBeInTheDocument();
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getByText("T?")).toBeInTheDocument();
  });
});
