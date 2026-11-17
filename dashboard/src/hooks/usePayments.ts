import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { useResource } from "../common";
export const usePayments = () => useResource(api.payments, "payments");
export function useCreatePayment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ amount, currency }: { amount: number; currency: string }) =>
      api.submit(amount, currency),
    onSuccess: () => client.invalidateQueries({ queryKey: ["payments"] }),
  });
}
