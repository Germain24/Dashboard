from sqlmodel import Session, select
from app.models.cuisine import Recipe


def create_recipe(session: Session, titre: str, portions: int = 4, temps_prep: int = 0,
                  temps_cuisson: int = 0, instructions: str = "",
                  source_url: str | None = None, image_url: str | None = None) -> Recipe:
    r = Recipe(titre=titre, portions=portions, temps_prep=temps_prep,
               temps_cuisson=temps_cuisson, instructions=instructions,
               source_url=source_url, image_url=image_url)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def get_recipes(session: Session, search: str | None = None) -> list[Recipe]:
    q = select(Recipe)
    if search:
        q = q.where(Recipe.titre.contains(search))
    return session.exec(q).all()


def import_from_url(url: str) -> dict | None:
    try:
        import httpx
        import json
        from bs4 import BeautifulSoup
        resp = httpx.get(url, timeout=10.0, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") == "Recipe":
                    yield_val = data.get("recipeYield", "4")
                    portions = int(yield_val) if str(yield_val).isdigit() else 4
                    instructions_raw = data.get("recipeInstructions") or []
                    instructions = "\n".join(
                        step.get("text", step) if isinstance(step, dict) else str(step)
                        for step in instructions_raw
                    )
                    image = data.get("image")
                    image_url = (image[0] if isinstance(image, list) else image) if image else None
                    return {
                        "titre": data.get("name", ""),
                        "portions": portions,
                        "instructions": instructions,
                        "image_url": image_url,
                        "source_url": url,
                    }
            except Exception:
                continue
        return None
    except Exception:
        return None
