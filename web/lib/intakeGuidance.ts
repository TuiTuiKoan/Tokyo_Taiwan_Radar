export const PURE_PUBLICATION_EVENT_FORM_GUIDANCE = `Pure publication vs physical event_form rule (must follow exactly):
- Use event_form=["publication"] only for metadata-only publication records (book/periodical listing) with no physical session.
- Pure publication records are metadata-only: keep publication date and publisher metadata only; treat venue/address/hours/price as non-required publication surfaces.
- If there is any physical session (book launch, release talk, signing, lecture, workshop, meetup, exhibition, screening, livestream schedule), do NOT include "publication" in event_form.
- Physical launch/talk/signing/lecture/workshop rows must use physical event forms (for example lecture/workshop/performance/conference/networking) and publication must be excluded.
`;