(() => {
  const proofNoPhoto = document.getElementById("id_proof_no_photo");
  const proofManual = document.querySelector("[data-proof-manual]");
  const proofPhoto = document.querySelector("[data-proof-photo]");

  const syncProofFields = () => {
    if (!proofNoPhoto || !proofManual || !proofPhoto) {
      return;
    }
    const useManualReference = proofNoPhoto.checked;
    proofManual.hidden = !useManualReference;
    proofPhoto.hidden = useManualReference;
  };

  syncProofFields();
  proofNoPhoto?.addEventListener("change", syncProofFields);

  document.querySelectorAll("[data-tracking-role-select]").forEach((roleSelect) => {
    roleSelect.addEventListener("change", () => {
      if (!roleSelect.value) {
        return;
      }
      const url = new URL(window.location.href);
      url.searchParams.set("role", roleSelect.value);
      window.location.href = url.toString();
    });
  });
})();
