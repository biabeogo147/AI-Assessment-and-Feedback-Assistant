# Docs Foundation Plan

## Muc tieu

Xay dung bo tai lieu nen tang cho giai doan dau cua project **AI Assessment and Feedback Assistant**. Bo tai lieu nay tap trung vao buc tranh tong quan nghiep vu va workflow, giup thanh vien tech va non-tech co cung mot cach hieu ve san pham truoc khi di vao kien truc, AI agent, API hoac data schema.

## Pham vi

Trong pham vi:

- Ghi lai cau truc docs lean cho giai doan dau.
- Tao tai lieu tong quan project.
- Tao tai lieu workflow nghiep vu tong quan.
- Tao Use Case Specification cho cac use case chinh.
- Tao cac diagram bang Draw.io de mo ta actors, use case, activity flow, swimlane workflow va domain context.

Ngoai pham vi:

- Khong thiet ke system architecture chi tiet.
- Khong thiet ke AI agent internals, prompt chain, tool calling hay model routing.
- Khong thiet ke API, database schema hoac data dictionary chi tiet.
- Khong tao deployment, runbook, observability hoac test strategy.
- Khong tao file Markdown rong hoac chi co heading.

## File se tao

```text
docs/
  plans/
    active/
      2026-07-14-docs-foundation-plan.md

  raw-idea/
    doc-structure.md

  overview/
    project-overview.md
    business-workflows.md
    use-case-specification.md

  diagrams/
    use-case.drawio
    activity-overview.drawio
    business-workflows.drawio
    domain-context.drawio
```

`docs/plans/completed/` se duoc su dung khi can chuyen active plan da hoan thanh sang khu vuc completed. Neu chua co completed plan, folder nay khong can co file Markdown rieng.

## Thu tu thuc hien

1. Tao active plan nay trong `docs/plans/active/`.
2. Tao `docs/raw-idea/doc-structure.md` de mo ta docs roadmap va quy uoc diagram.
3. Tao cac tai lieu overview co noi dung that:
   - `project-overview.md`
   - `business-workflows.md`
   - `use-case-specification.md`
4. Tao cac diagram Draw.io:
   - `use-case.drawio`
   - `activity-overview.drawio`
   - `business-workflows.drawio`
   - `domain-context.drawio`
5. Kiem tra lai:
   - Khong co Markdown rong.
   - Moi diagram duoc link tu it nhat mot tai lieu Markdown.
   - Cac docs khong di sau vao architecture, AI agent internals, API hoac data schema.

## Tieu chi hoan thanh

- Active plan ton tai truoc cac tai lieu moi khac.
- `doc-structure.md` noi ro moi file dung de lam gi va nen tao o giai doan nao.
- Ba tai lieu overview co noi dung doc duoc boi ca tech va non-tech.
- Bon file `.drawio` ton tai va co noi dung so do co the mo bang Draw.io.
- Cac diagram duoc nhac den trong tai lieu Markdown tuong ung.
- Nguoi doc co the hieu duoc:
  - Project giai quyet van de gi.
  - Actor chinh la ai.
  - Workflow tong quan dien ra nhu the nao.
  - Use case chinh gom nhung gi.
  - Khi nao giao vien can review.

## Trang thai

- [x] Tao active plan.
- [x] Tao docs roadmap trong `docs/raw-idea/doc-structure.md`.
- [x] Tao tai lieu tong quan project.
- [x] Tao tai lieu workflow nghiep vu.
- [x] Tao Use Case Specification.
- [x] Tao cac diagram Draw.io.
- [x] Chay kiem tra validation.

## Ghi chu thuc thi

- Ngon ngu tai lieu chinh la tieng Viet.
- Thuat ngu tieng Anh duoc giu khi no la thuat ngu chuyen mon pho bien, vi du: `Use Case`, `Activity Diagram`, `Teacher Review Queue`, `Mastery`.
- Draw.io `.drawio` la source of truth cho diagram.
- `docs/raw-idea/raw-idea.md` va `docs/raw-idea/raw-idea.png` duoc giu lai nhu input lich su, khong phai source of truth lau dai.
