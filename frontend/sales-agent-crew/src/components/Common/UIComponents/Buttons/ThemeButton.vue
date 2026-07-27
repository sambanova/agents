<template>
  <button
    :class="computedClass"
    :disabled="loading || disabled"
    @click="handleClick"
  >
    <span v-if="loading" class="loader"></span>
    <span v-else><slot /></span>
  </button>
</template>

<script>
export default {
  name: 'ThemeButton',
  props: {
    loading: {
      type: Boolean,
      default: false,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    customClass: {
      type: String,
      default: '',
    },
  },
  computed: {
    computedClass() {
      const baseClass =
        'bg-brand-primary text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline';
      const hoverClass = !this.loading && !this.disabled ? 'hover:primary-theme' : '';
      return `${baseClass} ${hoverClass} ${this.customClass}`;
    },
  },
  methods: {
    handleClick(event) {
      if (!this.loading && !this.disabled) {
        this.$emit('click', event);
      }
    },
  },
};
</script>

<style scoped>
.loader {
  border: 2px solid transparent;
  border-top: 2px solid white;
  border-radius: 50%;
  width: 1rem;
  height: 1rem;
  animation: spin 1s linear infinite;
  display: inline-block;
  margin-right: 0.5rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
