import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue';

export const useFullscreen = (target: Ref<HTMLElement | null>) => {
  const isFullscreen = ref(false);

  const onChange = () => {
    isFullscreen.value = document.fullscreenElement === target.value;
    document.body.style.overflow = isFullscreen.value ? 'hidden' : '';
  };

  const request = async () => {
    const el = target.value;
    if (!el?.requestFullscreen) return;
    await el.requestFullscreen().catch(() => {});
  };

  const exit = async () => {
    if (!document.fullscreenElement) return;
    await document.exitFullscreen().catch(() => {});
  };

  const toggle = async () => (isFullscreen.value ? exit() : request());

  onMounted(() => {
    document.addEventListener('fullscreenchange', onChange);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('fullscreenchange', onChange);
    document.body.style.overflow = '';
  });

  return { isFullscreen, request, exit, toggle };
};
