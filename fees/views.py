from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from decimal import Decimal
import json

from accounts.permissions import (
    InstitutionAccessMixin, IsInstitutionAccountantOrAdmin, is_platform_admin,
    user_can_access_institution, user_institution_ids, FinanceRequiredMixin,
    FinanceSelfServiceRequiredMixin, is_accountant_user
)
from .models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee, 
    Payment, Receipt, FeeDiscount, StudentFeeDiscount
)
from .forms import (
    FeeCategoryForm, FeeStructureForm, FeeStructureDetailForm, StudentFeeForm,
    PaymentForm, FeeDiscountForm, StudentFeeDiscountForm, StudentFeeSearchForm,
    PaymentSearchForm, FeeReportForm, BulkFeeGenerationForm, BulkPaymentForm
)
from .serializers import (
    FeeCategorySerializer, FeeStructureSerializer, FeeStructureDetailSerializer,
    StudentFeeSerializer, PaymentSerializer, PaymentCreateSerializer,
    ReceiptSerializer, FeeDiscountSerializer, StudentFeeDiscountSerializer,
    StudentFeeDiscountCreateSerializer, FeeCollectionSummarySerializer,
    OutstandingFeeSerializer, FeeReportSerializer, BulkFeeGenerationSerializer,
    BulkPaymentSerializer
)
from .services import PaymentRecordingError, create_receipt_for_payment, record_payment
from students.models import Student, Class, AcademicYear


def fee_balance_expression():
    return ExpressionWrapper(
        F('amount') - F('paid_amount'),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )


def outstanding_fee_total(queryset):
    return queryset.aggregate(total=Sum(fee_balance_expression()))['total'] or Decimal('0')


def student_institution_id(student):
    return getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)


def ensure_user_can_access_student(user, student, message):
    if not user_can_access_institution(user, student_institution_id(student)):
        raise PermissionDenied(message)


# API Viewsets
class FeeCategoryViewSet(viewsets.ModelViewSet):
    queryset = FeeCategory.objects.all()
    serializer_class = FeeCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = FeeCategory.objects.all()
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = FeeStructure.objects.select_related('academic_year', 'class_obj')
        institution_ids = getattr(self.request.user, 'institution_memberships', None)
        if not self.request.user.is_superuser and self.request.user.user_type != 'super_admin':
            ids = list(self.request.user.institution_memberships.filter(
                is_active=True, institution__is_active=True
            ).values_list('institution_id', flat=True))
            queryset = queryset.filter(academic_year__institution_id__in=ids) if ids else queryset.none()
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    def perform_create(self, serializer):
        academic_year = serializer.validated_data.get('academic_year')
        if not user_can_access_institution(self.request.user, getattr(academic_year, 'institution_id', None)):
            raise PermissionDenied('You cannot create fee structures for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        academic_year = serializer.validated_data.get('academic_year', serializer.instance.academic_year)
        if not user_can_access_institution(self.request.user, getattr(academic_year, 'institution_id', None)):
            raise PermissionDenied('You cannot move fee structures to this institution.')
        serializer.save()


class FeeStructureDetailViewSet(viewsets.ModelViewSet):
    queryset = FeeStructureDetail.objects.all()
    serializer_class = FeeStructureDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = FeeStructureDetail.objects.select_related('fee_structure__academic_year', 'fee_category')
        if not self.request.user.is_superuser and self.request.user.user_type != 'super_admin':
            ids = list(self.request.user.institution_memberships.filter(
                is_active=True, institution__is_active=True
            ).values_list('institution_id', flat=True))
            queryset = queryset.filter(fee_structure__academic_year__institution_id__in=ids) if ids else queryset.none()
        return queryset

    def perform_create(self, serializer):
        fee_structure = serializer.validated_data.get('fee_structure')
        if not user_can_access_institution(self.request.user, getattr(getattr(fee_structure, 'academic_year', None), 'institution_id', None)):
            raise PermissionDenied('You cannot create fee details for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        fee_structure = serializer.validated_data.get('fee_structure', serializer.instance.fee_structure)
        if not user_can_access_institution(self.request.user, getattr(getattr(fee_structure, 'academic_year', None), 'institution_id', None)):
            raise PermissionDenied('You cannot move fee details to this institution.')
        serializer.save()


class StudentFeeViewSet(viewsets.ModelViewSet):
    queryset = StudentFee.objects.all()
    serializer_class = StudentFeeSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = StudentFee.objects.select_related(
            'student__user', 'fee_structure_detail__fee_category',
            'student__current_class__academic_year__institution'
        )
        user = self.request.user
        if not user.is_superuser and user.user_type != 'super_admin':
            if user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif user.user_type == 'parent':
                queryset = queryset.filter(student__parents__user=user)
            else:
                ids = list(user.institution_memberships.filter(
                    is_active=True, institution__is_active=True
                ).values_list('institution_id', flat=True))
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=ids) if ids else queryset.none()
        student_id = self.request.query_params.get('student', None)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        return queryset

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        ensure_user_can_access_student(self.request.user, student, 'You cannot create fees for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        ensure_user_can_access_student(self.request.user, student, 'You cannot move fees to this institution.')
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get fee collection summary"""
        scoped_fees = self.get_queryset()
        scoped_student_ids = scoped_fees.values_list('student_id', flat=True)
        total_collection = Payment.objects.filter(
            student_id__in=scoped_student_ids,
            payment_status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_payments = Payment.objects.filter(
            student_id__in=scoped_student_ids,
            payment_status='completed',
        ).count()
        
        pending_amount = outstanding_fee_total(scoped_fees.filter(
            payment_status__in=['pending', 'partial']
        ))
        
        overdue_amount = outstanding_fee_total(scoped_fees.filter(
            payment_status__in=['pending', 'partial'],
            due_date__lt=timezone.now().date()
        ))
        
        data = {
            'total_collection': total_collection,
            'total_payments': total_payments,
            'pending_amount': pending_amount,
            'overdue_amount': overdue_amount,
            'period': 'All Time'
        }
        
        serializer = FeeCollectionSummarySerializer(data)
        return Response(serializer.data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'generate_receipt']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'student__user',
            'student__current_class__academic_year__institution',
            'received_by',
            'receipt',
        )
        user = self.request.user
        if user.is_superuser or user.user_type == 'super_admin':
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        ids = list(user.institution_memberships.filter(
            is_active=True, institution__is_active=True
        ).values_list('institution_id', flat=True))
        return queryset.filter(student__current_class__academic_year__institution_id__in=ids) if ids else queryset.none()

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        ensure_user_can_access_student(self.request.user, student, 'You cannot create payments for this institution.')
        serializer.save(received_by=self.request.user)

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        ensure_user_can_access_student(self.request.user, student, 'You cannot move payments to this institution.')
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def generate_receipt(self, request, pk=None):
        """Generate receipt for payment"""
        payment = self.get_object()
        receipt = create_receipt_for_payment(payment)
        
        serializer = ReceiptSerializer(receipt)
        return Response(serializer.data)


class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Receipt.objects.all()
    serializer_class = ReceiptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Receipt.objects.select_related(
            'payment__student__user', 'payment__student__current_class__academic_year__institution'
        )
        user = self.request.user
        if user.is_superuser or user.user_type == 'super_admin':
            return queryset
        if user.user_type == 'student':
            return queryset.filter(payment__student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(payment__student__parents__user=user)
        ids = list(user.institution_memberships.filter(
            is_active=True, institution__is_active=True
        ).values_list('institution_id', flat=True))
        return queryset.filter(payment__student__current_class__academic_year__institution_id__in=ids) if ids else queryset.none()


class FeeDiscountViewSet(viewsets.ModelViewSet):
    queryset = FeeDiscount.objects.all()
    serializer_class = FeeDiscountSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()


class StudentFeeDiscountViewSet(viewsets.ModelViewSet):
    queryset = StudentFeeDiscount.objects.all()
    serializer_class = StudentFeeDiscountSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionAccountantOrAdmin()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return StudentFeeDiscountCreateSerializer
        return StudentFeeDiscountSerializer
    
    def get_queryset(self):
        queryset = StudentFeeDiscount.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution', 'fee_discount', 'approved_by'
        )
        user = self.request.user
        if user.is_superuser or user.user_type == 'super_admin':
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        ids = list(user.institution_memberships.filter(
            is_active=True, institution__is_active=True
        ).values_list('institution_id', flat=True))
        return queryset.filter(student__current_class__academic_year__institution_id__in=ids) if ids else queryset.none()

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        ensure_user_can_access_student(self.request.user, student, 'You cannot create discounts for this institution.')
        serializer.save(approved_by=self.request.user)

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        ensure_user_can_access_student(self.request.user, student, 'You cannot move discounts to this institution.')
        serializer.save()


# Web-based Views
@login_required
@user_passes_test(is_accountant_user)
def fees_dashboard(request):
    """Fees dashboard with summary statistics"""
    # Get summary statistics
    total_collection = Payment.objects.filter(
        payment_status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    total_payments = Payment.objects.filter(payment_status='completed').count()
    
    pending_amount = outstanding_fee_total(StudentFee.objects.filter(
        payment_status__in=['pending', 'partial']
    ))
    
    overdue_amount = outstanding_fee_total(StudentFee.objects.filter(
        payment_status__in=['pending', 'partial'],
        due_date__lt=timezone.now().date()
    ))
    
    # Recent payments
    recent_payments = Payment.objects.select_related(
        'student__user', 'student__current_class'
    ).order_by('-payment_date')[:10]
    
    # Outstanding fees
    outstanding_fees = StudentFee.objects.select_related(
        'student__user', 'student__current_class', 'fee_structure_detail__fee_category'
    ).filter(
        payment_status__in=['pending', 'partial']
    ).order_by('due_date')[:10]
    
    context = {
        'total_collection': total_collection,
        'total_payments': total_payments,
        'pending_amount': pending_amount,
        'overdue_amount': overdue_amount,
        'recent_payments': recent_payments,
        'outstanding_fees': outstanding_fees,
    }
    
    return render(request, 'fees/dashboard.html', context)


class MyFeesView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, TemplateView):
    template_name = 'fees/my_fees.html'

    def get_fee_queryset(self):
        queryset = StudentFee.objects.select_related(
            'student__user',
            'student__current_class__academic_year__institution',
            'fee_structure_detail__fee_category',
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user).distinct()
        if is_accountant_user(user):
            institution_ids = user_institution_ids(user)
            return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        return queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_fees = self.get_fee_queryset().order_by('due_date')
        fee_totals = student_fees.aggregate(amount=Sum('amount'), paid=Sum('paid_amount'))
        payments = Payment.objects.filter(student_fee__in=student_fees).select_related(
            'student__user', 'student_fee'
        ).order_by('-payment_date')[:10]
        receipts = Receipt.objects.filter(payment__student_fee__in=student_fees).select_related(
            'payment__student__user'
        ).order_by('-receipt_date')[:10]
        context.update({
            'student_fees': student_fees,
            'payments': payments,
            'receipts': receipts,
            'total_fees': fee_totals['amount'] or 0,
            'total_paid': fee_totals['paid'] or 0,
            'total_balance': (fee_totals['amount'] or 0) - (fee_totals['paid'] or 0),
        })
        return context


class StudentFeeListView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, InstitutionAccessMixin, ListView):
    model = StudentFee
    template_name = 'fees/student_fee_list.html'
    context_object_name = 'student_fees'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = StudentFee.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'fee_structure_detail__fee_category'
        )
        user = self.request.user
        if not is_platform_admin(user):
            if user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif user.user_type == 'parent':
                queryset = queryset.filter(student__parents__user=user)
            elif is_accountant_user(user):
                institution_ids = user_institution_ids(user)
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
            else:
                queryset = queryset.none()
        
        # Apply filters
        form = StudentFeeSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('student'):
                queryset = queryset.filter(student=form.cleaned_data['student'])
            if form.cleaned_data.get('fee_category'):
                queryset = queryset.filter(fee_structure_detail__fee_category=form.cleaned_data['fee_category'])
            if form.cleaned_data.get('payment_status'):
                queryset = queryset.filter(payment_status=form.cleaned_data['payment_status'])
            if form.cleaned_data.get('due_date_from'):
                queryset = queryset.filter(due_date__gte=form.cleaned_data['due_date_from'])
            if form.cleaned_data.get('due_date_to'):
                queryset = queryset.filter(due_date__lte=form.cleaned_data['due_date_to'])
        
        return queryset.order_by('-due_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = StudentFeeSearchForm(self.request.GET)
        return context


class StudentFeeCreateView(LoginRequiredMixin, FinanceRequiredMixin, CreateView):
    model = StudentFee
    form_class = StudentFeeForm
    template_name = 'fees/student_fee_form.html'
    success_url = reverse_lazy('fees:student_fee_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Student fee created successfully.')
        return super().form_valid(form)


class StudentFeeUpdateView(LoginRequiredMixin, FinanceRequiredMixin, UpdateView):
    model = StudentFee
    form_class = StudentFeeForm
    template_name = 'fees/student_fee_form.html'
    success_url = reverse_lazy('fees:student_fee_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Student fee updated successfully.')
        return super().form_valid(form)


class StudentFeeDetailView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, DetailView):
    model = StudentFee
    template_name = 'fees/student_fee_detail.html'
    context_object_name = 'student_fee'
    
    def get_queryset(self):
        queryset = StudentFee.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'fee_structure_detail__fee_category'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if is_accountant_user(user):
            institution_ids = user_institution_ids(user)
            return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        return queryset.none()


class PaymentListView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, InstitutionAccessMixin, ListView):
    model = Payment
    template_name = 'fees/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution', 'received_by'
        )
        user = self.request.user
        if not is_platform_admin(user):
            if user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif user.user_type == 'parent':
                queryset = queryset.filter(student__parents__user=user)
            elif is_accountant_user(user):
                institution_ids = user_institution_ids(user)
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
            else:
                queryset = queryset.none()
        
        # Apply filters
        form = PaymentSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('student'):
                queryset = queryset.filter(student=form.cleaned_data['student'])
            if form.cleaned_data.get('payment_method'):
                queryset = queryset.filter(payment_method=form.cleaned_data['payment_method'])
            if form.cleaned_data.get('payment_status'):
                queryset = queryset.filter(payment_status=form.cleaned_data['payment_status'])
            if form.cleaned_data.get('payment_date_from'):
                queryset = queryset.filter(payment_date__date__gte=form.cleaned_data['payment_date_from'])
            if form.cleaned_data.get('payment_date_to'):
                queryset = queryset.filter(payment_date__date__lte=form.cleaned_data['payment_date_to'])
        
        return queryset.order_by('-payment_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PaymentSearchForm(self.request.GET)
        return context


class PaymentCreateView(LoginRequiredMixin, FinanceRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'fees/payment_form.html'
    success_url = reverse_lazy('fees:payment_list')
    
    def form_valid(self, form):
        try:
            self.object = record_payment(
                student=form.cleaned_data['student'],
                student_fee=form.cleaned_data['student_fee'],
                amount=form.cleaned_data['amount'],
                payment_method=form.cleaned_data['payment_method'],
                payment_status=form.cleaned_data['payment_status'],
                transaction_id=form.cleaned_data.get('transaction_id') or '',
                reference_number=form.cleaned_data.get('reference_number') or '',
                remarks=form.cleaned_data.get('remarks') or '',
                received_by=self.request.user,
            )
        except PaymentRecordingError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, 'Payment recorded successfully.')
        return redirect(self.get_success_url())


class PaymentDetailView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, DetailView):
    model = Payment
    template_name = 'fees/payment_detail.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        queryset = Payment.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution', 'received_by'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if is_accountant_user(user):
            institution_ids = user_institution_ids(user)
            return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        return queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['receipt'] = getattr(self.object, 'receipt', None)
        return context


class ReceiptListView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, ListView):
    model = Receipt
    template_name = 'fees/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20

    def get_queryset(self):
        viewset = ReceiptViewSet()
        viewset.request = self.request
        return viewset.get_queryset().order_by('-receipt_date')


class ReceiptDetailView(LoginRequiredMixin, FinanceSelfServiceRequiredMixin, DetailView):
    model = Receipt
    template_name = 'fees/receipt_detail.html'
    context_object_name = 'receipt'

    def get_queryset(self):
        viewset = ReceiptViewSet()
        viewset.request = self.request
        return viewset.get_queryset()


@login_required
@user_passes_test(is_accountant_user)
def bulk_fee_generation(request):
    """Bulk fee generation for multiple students"""
    if request.method == 'POST':
        form = BulkFeeGenerationForm(request.POST)
        if form.is_valid():
            fee_structure = form.cleaned_data['fee_structure']
            students = form.cleaned_data['students']
            due_date = form.cleaned_data['due_date']
            
            created_count = 0
            for student in students:
                for fee_detail in fee_structure.fee_details.all():
                    student_fee, created = StudentFee.objects.get_or_create(
                        student=student,
                        fee_structure_detail=fee_detail,
                        defaults={
                            'amount': fee_detail.amount,
                            'due_date': due_date,
                            'payment_status': 'pending'
                        }
                    )
                    if created:
                        created_count += 1
            
            messages.success(request, f'{created_count} fee records created successfully.')
            return redirect('fees:student_fee_list')
    else:
        form = BulkFeeGenerationForm()
    
    return render(request, 'fees/bulk_fee_generation.html', {'form': form})


@login_required
@user_passes_test(is_accountant_user)
def bulk_payment(request):
    """Bulk payment processing"""
    if request.method == 'POST':
        form = BulkPaymentForm(request.POST)
        if form.is_valid():
            student_fees = form.cleaned_data['student_fees']
            payment_method = form.cleaned_data['payment_method']
            transaction_id = form.cleaned_data.get('transaction_id', '')
            remarks = form.cleaned_data.get('remarks', '')
            
            created_count = 0
            failed_count = 0
            for student_fee in student_fees:
                try:
                    record_payment(
                        student=student_fee.student,
                        student_fee=student_fee,
                        amount=student_fee.balance_amount,
                        payment_method=payment_method,
                        payment_status=Payment.PaymentStatus.COMPLETED,
                        transaction_id=transaction_id,
                        remarks=remarks,
                        received_by=request.user,
                    )
                    created_count += 1
                except PaymentRecordingError:
                    failed_count += 1
            
            messages.success(request, f'{created_count} payments processed successfully.')
            if failed_count:
                messages.warning(request, f'{failed_count} payments were skipped because the outstanding balance changed.')
            return redirect('fees:payment_list')
    else:
        form = BulkPaymentForm()
    
    return render(request, 'fees/bulk_payment.html', {'form': form})


@login_required
@user_passes_test(is_accountant_user)
def fee_report(request):
    """Generate fee reports"""
    if request.method == 'POST':
        form = FeeReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            academic_year = form.cleaned_data.get('academic_year')
            class_obj = form.cleaned_data.get('class_obj')
            fee_category = form.cleaned_data.get('fee_category')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            # Generate report data based on type
            if report_type == 'collection':
                report_data = generate_collection_report(
                    academic_year, class_obj, fee_category, date_from, date_to
                )
            elif report_type == 'outstanding':
                report_data = generate_outstanding_report(
                    academic_year, class_obj, fee_category
                )
            elif report_type == 'discount':
                report_data = generate_discount_report(
                    academic_year, class_obj, date_from, date_to
                )
            else:  # summary
                report_data = generate_summary_report(
                    academic_year, class_obj, date_from, date_to
                )
            
            context = {
                'form': form,
                'report_data': report_data,
                'report_type': report_type,
                'date_from': date_from,
                'date_to': date_to
            }
            return render(request, 'fees/fee_report.html', context)
    else:
        form = FeeReportForm()
    
    return render(request, 'fees/fee_report.html', {'form': form})


# Helper functions for reports
def generate_collection_report(academic_year, class_obj, fee_category, date_from, date_to):
    """Generate fee collection report"""
    payments = Payment.objects.filter(payment_status='completed')
    
    if academic_year:
        payments = payments.filter(student__current_class__academic_year=academic_year)
    if class_obj:
        payments = payments.filter(student__current_class=class_obj)
    if fee_category:
        payments = payments.filter(student_fee__fee_structure_detail__fee_category=fee_category)
    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
    
    return payments.select_related('student__user', 'student__current_class')


def generate_outstanding_report(academic_year, class_obj, fee_category):
    """Generate outstanding fees report"""
    student_fees = StudentFee.objects.filter(
        payment_status__in=['pending', 'partial']
    )
    
    if academic_year:
        student_fees = student_fees.filter(student__current_class__academic_year=academic_year)
    if class_obj:
        student_fees = student_fees.filter(student__current_class=class_obj)
    if fee_category:
        student_fees = student_fees.filter(fee_structure_detail__fee_category=fee_category)
    
    return student_fees.select_related(
        'student__user', 'student__current_class', 'fee_structure_detail__fee_category'
    )


def generate_discount_report(academic_year, class_obj, date_from, date_to):
    """Generate discount report"""
    discounts = StudentFeeDiscount.objects.all()
    
    if academic_year:
        discounts = discounts.filter(student__current_class__academic_year=academic_year)
    if class_obj:
        discounts = discounts.filter(student__current_class=class_obj)
    if date_from:
        discounts = discounts.filter(approved_at__date__gte=date_from)
    if date_to:
        discounts = discounts.filter(approved_at__date__lte=date_to)
    
    return discounts.select_related(
        'student__user', 'student__current_class', 'fee_discount', 'approved_by'
    )


def generate_summary_report(academic_year, class_obj, date_from, date_to):
    """Generate summary report"""
    # This would return aggregated data
    payments = Payment.objects.filter(payment_status='completed')
    outstanding = StudentFee.objects.filter(payment_status__in=['pending', 'partial'])
    discounts = StudentFeeDiscount.objects.all()

    if academic_year:
        payments = payments.filter(student__current_class__academic_year=academic_year)
        outstanding = outstanding.filter(student__current_class__academic_year=academic_year)
        discounts = discounts.filter(student__current_class__academic_year=academic_year)
    if class_obj:
        payments = payments.filter(student__current_class=class_obj)
        outstanding = outstanding.filter(student__current_class=class_obj)
        discounts = discounts.filter(student__current_class=class_obj)
    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
        discounts = discounts.filter(approved_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
        discounts = discounts.filter(approved_at__date__lte=date_to)

    return {
        'total_collection': payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0'),
        'total_outstanding': outstanding_fee_total(outstanding),
        'total_discounts': discounts.aggregate(
            total=Sum('discount_amount')
        )['total'] or Decimal('0'),
    }


# AJAX views
@login_required
def get_students_for_fee_structure(request):
    """Get students for a specific fee structure"""
    fee_structure_id = request.GET.get('fee_structure_id')
    if fee_structure_id:
        try:
            fee_structure = FeeStructure.objects.get(id=fee_structure_id)
            students = Student.objects.filter(current_class=fee_structure.class_obj)
            data = [{'id': student.id, 'name': student.user.get_full_name()} for student in students]
            return JsonResponse({'students': data})
        except FeeStructure.DoesNotExist:
            return JsonResponse({'error': 'Fee structure not found'}, status=404)
    return JsonResponse({'error': 'Fee structure ID required'}, status=400)


@login_required
def get_student_fees(request):
    """Get fees for a specific student"""
    student_id = request.GET.get('student_id')
    if student_id:
        try:
            student = Student.objects.get(id=student_id)
            student_fees = StudentFee.objects.filter(
                student=student,
                payment_status__in=['pending', 'partial']
            ).select_related('fee_structure_detail__fee_category')
            
            data = [{
                'id': fee.id,
                'fee_category': fee.fee_structure_detail.fee_category.name,
                'amount': float(fee.amount),
                'balance_amount': float(fee.balance_amount),
                'due_date': fee.due_date.strftime('%Y-%m-%d')
            } for fee in student_fees]
            
            return JsonResponse({'student_fees': data})
        except Student.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)
    return JsonResponse({'error': 'Student ID required'}, status=400)
