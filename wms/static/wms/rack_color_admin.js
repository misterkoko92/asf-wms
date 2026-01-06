document.addEventListener("DOMContentLoaded", () => {
  const picker = document.querySelector("#id_color_picker");
  const textInput = document.querySelector("#id_color");
  if (!picker || !textInput) {
    return;
  }
  const isHex = (value) => /^#[0-9a-fA-F]{6}$/.test(value);

  if (isHex(textInput.value)) {
    picker.value = textInput.value;
  }

  picker.addEventListener("input", () => {
    textInput.value = picker.value;
  });

  textInput.addEventListener("input", () => {
    if (isHex(textInput.value)) {
      picker.value = textInput.value;
    }
  });
});
